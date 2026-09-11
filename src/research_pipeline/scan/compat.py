"""V2 compatibility check for synthesized harnesses.

The LLM (step 3) returns a synthesized harness as text. Before spending an
ESBMC run on it, reject the harnesses ESBMC-Python cannot handle:

- does not parse                         -> invalid_harness
- imports anything                       -> invalid_harness (not self-contained)
- references numpy / pandas / torch / tf -> unsupported_harness
- contains a for/while loop              -> invalid_harness
- references a name never bound in the
  harness (external helper, unimported
  type, project class)                   -> invalid_harness
- no module-level driver (a call or a
  `main()` invoked at module level)      -> invalid_harness
- `incorrect_result`/`assertion_violation` category, bare boolean assert over
  a fully unconstrained input, no domain assume, no buggy-vs-expected
  comparison                             -> invalid_harness

The last rule encodes a gotcha found while building harnesses by hand this
project: ESBMC-Python only registers the `nondet_*` / `__ESBMC_assume`
intrinsics when execution is driven from module level, not under `--function`.

Pure AST. No LLM, no ESBMC, no network.
"""

from __future__ import annotations

import ast
import builtins
import re
from dataclasses import dataclass, field
from itertools import pairwise

# Bare intrinsics a valid harness uses without importing them. Names taken from
# src/python-frontend/models/esbmc.py and function_call/builder.h (the intrinsic
# set the frontend actually registers).
_ALLOWED_UNDEFINED = frozenset(
    {
        "nondet_int",
        "nondet_float",
        "nondet_bool",
        "nondet_str",
        "nondet_list",
        "nondet_dict",
        "__ESBMC_assume",
        "__ESBMC_assert",
        "__ESBMC_cover",
        "__ESBMC_unreachable",
        "__ESBMC_requires",
        "__ESBMC_ensures",
        "__ESBMC_assigns",
    }
)

# Names that mean the harness leaked a heavy dependency ESBMC-Python does not model.
_UNSUPPORTED_NAMES = frozenset({"numpy", "np", "pandas", "pd", "torch", "tf", "tensorflow", "scipy"})

# Builtins the frontend does not model at all (not merely restricted). `sorted`,
# `sum`, `any`, `all`, `enumerate`, `min`, `max`, `divmod`, `range` ARE modelled
# with documented restrictions (limitations.md, README.md line 263) and stay off
# this list; the synth prompt still steers away from them, but a harness that
# uses one is not rejected here.
_UNSUPPORTED_BUILTINS = frozenset({"zip", "map", "filter", "reversed"})

# The real nondet intrinsics (models/esbmc.py). `__ESBMC_nondet_*` and
# `nondet_uint` are common LLM hallucinations and are NOT valid.
_VALID_NONDET = frozenset(
    {"nondet_int", "nondet_float", "nondet_bool", "nondet_str", "nondet_list", "nondet_dict"}
)
_BAD_NONDET = re.compile(
    r"\b__ESBMC_nondet_\w+|\bnondet_(?!int\b|float\b|bool\b|str\b|list\b|dict\b)\w+"
)

# Categories where the bug is "wrong output for a valid input", not "missing
# precondition check". These require either a domain assume or a buggy-vs-
# expected comparison (see _unconstrained_outcome_reasons); the other
# categories (invalid_precondition, none_misuse, variable_misuse, type_mismatch)
# correctly assert a bare boolean over unconstrained input by design -- that IS
# the bug (an unchecked precondition lets a bad value through).
#
# Public: the scan pipeline also uses this set to require differential grounding
# before counting a solver failure as a strong confirmation. An LLM can satisfy
# this module's basic structural check (any assume, any comparison) without the
# harness being semantically grounded (EXP-03, docs/v2/experiment_log.md,
# 2026-09-04: `assert matched == expected` with `expected: bool = True` passes a
# naive comparison check but is exactly as vacuous as the bare assert it replaced).
OUTCOME_CATEGORIES = frozenset({"incorrect_result", "assertion_violation"})

VERDICT_OK = "ok"
VERDICT_INVALID = "invalid_harness"
VERDICT_UNSUPPORTED = "unsupported_harness"
EXPECTED_PROPERTY_MARKER = "LLM_ESBMC_EXPECTED_PROPERTY"


@dataclass
class CompatResult:
    """Outcome of the compatibility check for one synthesized harness."""

    ok: bool
    verdict: str            # VERDICT_OK | VERDICT_INVALID | VERDICT_UNSUPPORTED
    reasons: list[str] = field(default_factory=list)


@dataclass
class OutcomeGroundingResult:
    """Whether an outcome-category assertion has an independent oracle side."""

    ok: bool
    reasons: list[str] = field(default_factory=list)


def _has_module_level_driver(tree: ast.Module) -> bool:
    """True if the module runs something at import time (Expr call or `main()`)."""
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            return True
        if isinstance(node, ast.If):
            # `if __name__ == "__main__": main()` also counts as a driver.
            for inner in ast.walk(node):
                if isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Call):
                    return True
    return False


def _bounded_loop_reasons(tree: ast.Module) -> list[str]:
    """Allow exactly one non-nested ``for`` over a constant ``range()``; reject the rest.

    The loop harness style keeps one real loop so a bug between adjacent
    container elements or across iterations stays expressible. The bound must be
    a literal so ESBMC's incremental unwinding actually terminates.
    """
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.AsyncFor, ast.While))]
    if not loops:
        return []
    if len(loops) > 1:
        return ["contains more than one loop (loop harness allows exactly one)"]
    loop = loops[0]
    if not isinstance(loop, ast.For):
        return ["loop harness allows only a `for` loop, not `while`/`async for`"]
    it = loop.iter
    if not (
        isinstance(it, ast.Call)
        and isinstance(it.func, ast.Name)
        and it.func.id == "range"
        and it.args
        and all(isinstance(a, ast.Constant) and isinstance(a.value, int) for a in it.args)
    ):
        return ["loop harness `for` must iterate `range(<int literal>...)`"]
    return []


def check_harness(
    source: str, *, category: str | None = None, allow_bounded_loop: bool = False
) -> CompatResult:
    """Return a CompatResult for a synthesized harness given as text.

    ``category`` is the candidate's hypothesis category (e.g. "incorrect_result").
    When given, it gates the outcome-comparison check (see
    ``_unconstrained_outcome_reasons``).

    ``allow_bounded_loop`` relaxes the no-loop rule for the loop harness style:
    one non-nested ``for`` over a constant ``range()`` is permitted.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return CompatResult(False, VERDICT_INVALID, [f"does not parse: {exc.msg}"])

    reasons: list[str] = []

    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    if imports:
        names = sorted(
            {
                (alias.name if isinstance(node, ast.Import) else node.module or "")
                for node in imports
                for alias in node.names
            }
        )
        reasons.append(f"imports {', '.join(n for n in names if n)}")
        return CompatResult(False, VERDICT_INVALID, reasons)

    if allow_bounded_loop:
        loop_reasons = _bounded_loop_reasons(tree)
        if loop_reasons:
            return CompatResult(False, VERDICT_INVALID, loop_reasons)
    elif any(isinstance(node, (ast.For, ast.AsyncFor, ast.While)) for node in ast.walk(tree)):
        return CompatResult(
            False,
            VERDICT_INVALID,
            ["contains a loop (scan harnesses must model only the scalar suspect expression)"],
        )

    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    referenced |= {
        node.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }
    leaked = sorted(referenced & _UNSUPPORTED_NAMES)
    if leaked:
        return CompatResult(
            False, VERDICT_UNSUPPORTED, [f"references unsupported dependency: {', '.join(leaked)}"]
        )

    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    bad_builtins = sorted(called & _UNSUPPORTED_BUILTINS)
    if bad_builtins:
        return CompatResult(
            False, VERDICT_UNSUPPORTED,
            [f"uses builtin ESBMC-Python does not model: {', '.join(bad_builtins)}"],
        )

    bad_nondet = sorted(set(_BAD_NONDET.findall(source)))
    if bad_nondet:
        return CompatResult(
            False, VERDICT_INVALID,
            [f"invalid nondet intrinsic name(s): {', '.join(bad_nondet)} (use nondet_int/float/bool/str)"],
        )

    if not _has_module_level_driver(tree):
        return CompatResult(
            False,
            VERDICT_INVALID,
            ["no module-level driver (harness must call the function at module level)"],
        )

    assertion_reasons = _check_expected_assertion(tree)
    if assertion_reasons:
        return CompatResult(False, VERDICT_INVALID, assertion_reasons)

    outcome_reasons = _unconstrained_outcome_reasons(tree, category)
    if outcome_reasons:
        return CompatResult(False, VERDICT_INVALID, outcome_reasons)

    type_reasons = _check_scalar_types(tree)
    if type_reasons:
        return CompatResult(False, VERDICT_INVALID, type_reasons)

    undefined = sorted(_undefined_names(tree))
    if undefined:
        return CompatResult(
            False,
            VERDICT_INVALID,
            [
                "references undefined name(s): " + ", ".join(undefined)
                + " (harness cannot import; every name must be a bound local, an"
                " ESBMC intrinsic, or a builtin)"
            ],
        )

    return CompatResult(True, VERDICT_OK, [])


def _check_expected_assertion(tree: ast.Module) -> list[str]:
    """Require one unmistakable user property and no unmarked assertions."""
    assertions = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    marked = [
        node
        for node in assertions
        if isinstance(node.msg, ast.Constant)
        and node.msg.value == EXPECTED_PROPERTY_MARKER
    ]
    if len(marked) != 1:
        return [
            (
                "harness must contain exactly one expected assertion written as "
                f'assert <condition>, "{EXPECTED_PROPERTY_MARKER}"'
            )
        ]
    if len(assertions) != 1:
        return ["harness contains additional unmarked assertions"]
    return []


def _annotation_name(annotation: ast.expr | None) -> str | None:
    if isinstance(annotation, ast.Name):
        return annotation.id
    return None


def _infer_expr_type(node: ast.expr, known: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return {
            "nondet_int": "int", "nondet_float": "float",
            "nondet_bool": "bool", "nondet_str": "str",
            "int": "int", "float": "float", "bool": "bool", "str": "str",
            "abs": _infer_expr_type(node.args[0], known) if node.args else None,
        }.get(node.func.id)
    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Dict):
        return "dict"
    if isinstance(node, ast.Tuple):
        return "tuple"
    return None


def _check_scalar_types(tree: ast.Module) -> list[str]:
    """Catch deterministic type errors that ESBMC may turn into false failures."""
    known: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            annotated = _annotation_name(node.annotation)
            if annotated:
                known[node.arg] = annotated
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotated = _annotation_name(node.annotation)
            inferred = _infer_expr_type(node.value, known) if node.value else None
            known[node.target.id] = annotated or inferred or known.get(node.target.id, "")
        elif isinstance(node, ast.Assign):
            inferred = _infer_expr_type(node.value, known)
            if inferred:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        known[target.id] = inferred

    reasons: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "abs":
            operand_type = _infer_expr_type(node.args[0], known) if node.args else None
            if operand_type not in {None, "int", "float", "bool"}:
                reasons.append(f"abs() receives {operand_type}, expected a numeric value")
        elif isinstance(node, ast.Subscript):
            value_type = _infer_expr_type(node.value, known)
            if value_type in {"int", "float", "bool"}:
                reasons.append(f"attempts to subscript non-container value of type {value_type}")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) == 2
        ):
            reasons.extend(_tautological_isinstance_reasons(node, known))
        elif isinstance(node, ast.Compare):
            reasons.extend(_tautological_str_coercion_reasons(node, known))
    return list(dict.fromkeys(reasons))


def _tautological_str_coercion_reasons(compare: ast.Compare, known: dict[str, str]) -> list[str]:
    """`str(x) == x` (or `!=`) is always False in real Python whenever `x` is
    int/float/bool -- a string is never equal to a number, independent of
    value, so the comparison carries zero information about the hypothesized
    bug. Confirmed on real code 2026-09-05: a synthesized harness for tqdm's
    `_is_utf` modeled `encoding_is_text: bool = str(encoding) == encoding`
    (encoding: int) and asserted it -- always-False by construction, same
    vacuous-comparison failure EXP-03 found in assertion_violation/
    incorrect_result (docs/v2/experiment_log.md), but here in type_mismatch,
    proving the pattern is not scoped to those two categories.
    """
    if len(compare.ops) != 1 or not isinstance(compare.ops[0], (ast.Eq, ast.NotEq)):
        return []
    sides = [compare.left, compare.comparators[0]]
    for coerced, other in (sides, sides[::-1]):
        if (
            isinstance(coerced, ast.Call)
            and isinstance(coerced.func, ast.Name)
            and coerced.func.id == "str"
            and len(coerced.args) == 1
            and isinstance(coerced.args[0], ast.Name)
            and isinstance(other, ast.Name)
            and coerced.args[0].id == other.id
            and known.get(other.id) in {"int", "float", "bool"}
        ):
            return [
                (
                    f"str({other.id}) == {other.id} is always False -- a string is never "
                    f"equal to a value of type {known[other.id]}, independent of the value; "
                    "this comparison carries no information about the hypothesized bug"
                )
            ]
    return []


def _tautological_isinstance_reasons(call: ast.Call, known: dict[str, str]) -> list[str]:
    """isinstance(x, T) is always True in a scan harness whenever x's own
    declared/inferred type already IS T -- ESBMC-Python gives every variable a
    fixed static type (no real dynamic typing), so this never tests anything.
    Confirmed empirically 2026-09-04 (EXP-02, docs/v2/experiment_log.md): a
    parameter typed `bool` and checked with `isinstance(param, bool)` always
    verifies SUCCESSFUL, hiding the type_mismatch/assertion_violation bug the
    harness meant to model.
    """
    target = call.args[0]
    if not isinstance(target, ast.Name):
        return []
    target_type = known.get(target.id)
    if not target_type:
        return []
    type_arg = call.args[1]
    checked_types: list[str] = []
    if isinstance(type_arg, ast.Name):
        checked_types = [type_arg.id]
    elif isinstance(type_arg, ast.Tuple):
        checked_types = [elt.id for elt in type_arg.elts if isinstance(elt, ast.Name)]
    if target_type in checked_types:
        return [
            (
                f"isinstance({target.id}, {target_type}) is always True here - "
                f"{target.id} is already declared/inferred as {target_type}, ESBMC-Python "
                "gives it no other possible type; model the wrong-type case with a "
                "differently-typed nondet_*() value instead"
            )
        ]
    return []


def _has_assume_call(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "__ESBMC_assume"
        for node in ast.walk(tree)
    )


def _direct_constant_names(tree: ast.Module) -> set[str]:
    """Names bound to a bare literal (`expected: bool = True`), never derived
    from a nondet_*() or computed -- lets _unconstrained_outcome_reasons catch
    `assert buggy == expected` where `expected` is a hardcoded constant wearing
    an oracle's clothes, not a real correct-value computation. Confirmed
    empirically 2026-09-04 (EXP-03, docs/v2/experiment_log.md): re-running the
    pipeline after this module first required "a comparison" produced exactly
    this shape (`expected: bool = True; assert matched == expected`) -- as
    vacuous as the bare assert it replaced, but now passing an Eq comparison.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Constant):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _is_hardcoded_side(expr: ast.expr, constant_names: set[str]) -> bool:
    return isinstance(expr, ast.Constant) or (
        isinstance(expr, ast.Name) and expr.id in constant_names
    )


def _is_nondet_call(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in _VALID_NONDET


def _expr_type(expr: ast.expr, origins: dict[str, str]) -> str:
    if isinstance(expr, ast.Constant):
        return "constant"
    if isinstance(expr, ast.Name):
        return origins.get(expr.id, "raw")
    if _is_nondet_call(expr):
        return "nondet"
    if isinstance(expr, ast.Call):
        return "call"
    if isinstance(expr, ast.Compare):
        return "computed"
    if isinstance(expr, (ast.BinOp, ast.BoolOp, ast.UnaryOp, ast.IfExp, ast.Subscript, ast.Attribute)):
        return "computed"
    names = [n.id for n in ast.walk(expr) if isinstance(n, ast.Name)]
    if any(origins.get(name) in {"computed", "call"} for name in names):
        return "computed"
    if any(origins.get(name) == "nondet" for name in names):
        return "raw"
    return "computed"


def _expr_names(expr: ast.expr) -> set[str]:
    return {node.id for node in ast.walk(expr) if isinstance(node, ast.Name)}


def _assigned_origins(tree: ast.Module) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Best-effort name origin for grounding outcome assertions."""
    origins: dict[str, str] = {}
    deps: dict[str, set[str]] = {}
    for _ in range(2):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            origin = _expr_type(value, origins)
            value_deps = set(_expr_names(value))
            for name in list(value_deps):
                value_deps.update(deps.get(name, set()))
            for target in targets:
                if isinstance(target, ast.Name):
                    origins[target.id] = origin
                    deps[target.id] = value_deps - {target.id}
    return origins, deps


def _comparison_pairs(compare: ast.Compare) -> list[tuple[ast.expr, ast.expr]]:
    sides = [compare.left, *compare.comparators]
    return list(pairwise(sides))


def _expr_deps(expr: ast.expr, deps: dict[str, set[str]]) -> set[str]:
    names = _expr_names(expr)
    out = set(names)
    for name in names:
        out.update(deps.get(name, set()))
    return out


def _has_differential_comparison(
    assertion: ast.Assert, origins: dict[str, str], deps: dict[str, set[str]]
) -> bool:
    for compare in [n for n in ast.walk(assertion.test) if isinstance(n, ast.Compare)]:
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in compare.ops):
            continue
        for left, right in _comparison_pairs(compare):
            left_type = _expr_type(left, origins)
            right_type = _expr_type(right, origins)
            if {left_type, right_type} <= {"constant", "nondet", "raw"}:
                continue
            if left_type in {"constant", "nondet"} or right_type in {"constant", "nondet"}:
                continue
            if ast.dump(left) == ast.dump(right):
                continue
            left_names = _expr_names(left)
            right_names = _expr_names(right)
            if left_names & _expr_deps(right, deps) or right_names & _expr_deps(left, deps):
                continue
            if "call" in {left_type, right_type} or "computed" in {left_type, right_type}:
                return True
    return False


def check_outcome_grounding(source: str) -> OutcomeGroundingResult:
    """Accept only outcome assertions with a separately computed comparison.

    `assertion_violation` and `incorrect_result` are about wrong behavior for a
    valid input. A solver failure is strong evidence only when the harness
    compares the buggy result with a second computation, such as a fixed/oracle
    expression. Bare booleans, constants and raw nondet values are kept as
    `confirmed_unverified`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return OutcomeGroundingResult(False, [f"does not parse: {exc.msg}"])
    origins, deps = _assigned_origins(tree)
    assertions = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    if any(_has_differential_comparison(assertion, origins, deps) for assertion in assertions):
        return OutcomeGroundingResult(True, [])
    return OutcomeGroundingResult(
        False,
        [
            (
                "outcome-category confirmation has no differential assertion "
                "(compare the buggy result with a separately computed expected value)"
            )
        ],
    )


def _unconstrained_outcome_reasons(tree: ast.Module, category: str | None) -> list[str]:
    """`incorrect_result`/`assertion_violation` harnesses claim the real function
    returns the wrong value for some input the real caller can actually produce.
    Proving that requires either restricting the input domain to what the real
    caller guarantees (`__ESBMC_assume`), or comparing the buggy expression
    against an explicit expected value/oracle -- the pattern used in the
    hand-made reference harnesses (`dataset/v2_real_world/bugs/*.py`):
    `assert buggy_result == correct_result`.

    Without either, the marked assert claims a bare boolean/negation holds for
    every value a fully free `nondet_*()` can take -- falsifiable by a
    fabricated input unrelated to the real bug. Confirmed empirically
    2026-09-04 (EXP-03, docs/v2/experiment_log.md): `assert "php -s" in script`
    over an unconstrained `nondet_str()` "confirms" on the empty string, which
    has nothing to do with the real bug (BugsInPy thefuck #7, about flags
    separated by other arguments).
    """
    if category not in OUTCOME_CATEGORIES:
        return []
    if _has_assume_call(tree):
        return []
    marked = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert)
        and isinstance(node.msg, ast.Constant)
        and node.msg.value == EXPECTED_PROPERTY_MARKER
    ]
    if len(marked) != 1:
        return []
    test = marked[0].test
    if isinstance(test, ast.Compare):
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in test.ops):
            return []
        constant_names = _direct_constant_names(tree)
        sides = [test.left, *test.comparators]
        if not any(_is_hardcoded_side(side, constant_names) for side in sides):
            return []
        return [
            (
                f"category '{category}' compares the buggy expression against a "
                "hardcoded constant, not a computed expected value -- that is the "
                "same unconstrained-input problem wearing a comparison's clothes; "
                "compute the expected/correct value from the input instead"
            )
        ]
    return [
        (
            f"category '{category}' asserts a bare boolean over a fully unconstrained "
            "input with no __ESBMC_assume and no buggy-vs-expected comparison -- add "
            "a domain assume or compare against an explicit expected value/oracle"
        )
    ]


def _undefined_names(tree: ast.Module) -> set[str]:
    """Names used but never bound in the harness, minus the allowed intrinsics."""
    bound: set[str] = set()
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                bound.add(node.id)
            else:
                used.add(node.id)

    return used - bound - _ALLOWED_UNDEFINED - set(dir(builtins))


def undefined_names(source: str) -> set[str]:
    """Names used but never bound in the harness, minus the allowed intrinsics.

    Exposed for the scan report; check_harness() rejects on this internally.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return _undefined_names(tree)
