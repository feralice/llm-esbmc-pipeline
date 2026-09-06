"""V2 compatibility check for the verbatim-slice harness (STYLE_DRIVER).

The driver method does not reconstruct the suspect expression from scratch (that
is the scalar synth, compat.py). It keeps the *smallest runnable slice* around
the bug -- the suspect line plus the lines feeding its operands -- verbatim from
the real source, replacing only the operands that come from an object, a
container, or an external call with a fresh ``nondet_*()``. Everything else in
the function is dropped.

So the one question this checker answers is: *did the LLM keep the real
arithmetic, or did it quietly reimplement it?*

Enforced:

- parses, non-empty; no imports (intrinsics are bare); no runtime ``def``
  shadowing an ESBMC intrinsic (reference PoC RETROSPECTIVE.md Finding 1);
- the suspect expression's operator skeleton survives in the harness -- every
  arithmetic / comparison operator and called-builtin in the real expression
  appears at least as often (subscripts, attributes and calls collapsed to a
  placeholder first, so ``x[i] - x[i-1]`` and ``a - b`` compare equal). When the
  candidate's ``expression`` is prose rather than code, fall back to requiring
  one real source line to survive with >= 0.55 token overlap;
- a module-level ``main()`` driver that calls the slice, binds the result, and
  asserts a property referencing it (liveness);
- no ``__ESBMC_cover`` (plain ``assert`` only); no numpy / pandas / torch.

Pure AST. No LLM, no ESBMC, no network.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field

from .compat import _UNSUPPORTED_NAMES, _has_module_level_driver

VERDICT_OK = "ok"
VERDICT_INVALID = "invalid_harness"
VERDICT_UNSUPPORTED = "unsupported_harness"

_INTRINSIC_NAMES = frozenset(
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
    }
)

_LINE_OVERLAP_MIN = 0.55

_OP_NAMES = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//",
    ast.Mod: "%", ast.Pow: "**", ast.LShift: "<<", ast.RShift: ">>",
    ast.BitOr: "|", ast.BitAnd: "&", ast.BitXor: "^",
    ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
    ast.Is: "is", ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in",
    ast.And: "and", ast.Or: "or", ast.USub: "u-", ast.Not: "not",
}
# Calls that shape the semantics of the checked expression. `len`/`int`/`abs`/...
# in the real line must still be in the harness line.
_SHAPING_CALLS = {"len", "int", "float", "bool", "str", "abs", "min", "max", "isinstance", "ord"}


@dataclass
class DriverCheckResult:
    ok: bool
    verdict: str
    reasons: list[str] = field(default_factory=list)


class _CollapseAccess(ast.NodeTransformer):
    """Replace every subscript / attribute / non-shaping call with a bare name,
    so `x[ind] - x[ind - 1]` and `a - b` collapse to the same skeleton."""

    def visit_Subscript(self, node):
        return ast.Name(id="_")

    def visit_Attribute(self, node):
        return ast.Name(id="_")

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in _SHAPING_CALLS:
            self.generic_visit(node)
            return node
        return ast.Name(id="_")


def _op_multiset(node: ast.AST) -> list[str]:
    ops: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, (ast.BinOp, ast.UnaryOp)):
            ops.append(_OP_NAMES.get(type(sub.op), "?"))
        elif isinstance(sub, ast.BoolOp):
            ops.extend([_OP_NAMES.get(type(sub.op), "?")] * (len(sub.values) - 1))
        elif isinstance(sub, ast.Compare):
            ops.extend(_OP_NAMES.get(type(o), "?") for o in sub.ops)
        elif (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id in _SHAPING_CALLS
        ):
            ops.append(f"call:{sub.func.id}")
    return ops


def _skeleton(code: str) -> list[str] | None:
    """Operator multiset of a code expression/statement, or None if it is prose."""
    try:
        tree = ast.parse(code.strip())
    except SyntaxError:
        return None
    if not tree.body:
        return None
    collapsed = _CollapseAccess().visit(tree)
    ast.fix_missing_locations(collapsed)
    return _op_multiset(collapsed)


def _multiset_covered(need: list[str], have: list[str]) -> bool:
    have = list(have)
    for op in need:
        if op in have:
            have.remove(op)
        else:
            return False
    return True


def _token_overlap(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _shadows_intrinsic(tree: ast.Module) -> list[str]:
    return sorted(
        {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name in _INTRINSIC_NAMES
        }
    )


def _result_is_live(tree: ast.Module) -> bool:
    """True if a non-intrinsic call's return is bound to a name and asserted on."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not isinstance(value, ast.Call):
            continue
        callee = value.func
        if not isinstance(callee, ast.Name) or callee.id in _INTRINSIC_NAMES:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            if names & bound:
                return True
    return False


def _type_map(tree: ast.Module) -> dict[str, str]:
    """Best-effort name -> declared/inferred scalar type for the harness."""
    nondet_ret = {
        "nondet_int": "int", "nondet_float": "float",
        "nondet_bool": "bool", "nondet_str": "str",
    }
    known: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and isinstance(node.annotation, ast.Name):
            known[node.arg] = node.annotation.id
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.annotation, ast.Name)
        ):
            known[node.target.id] = node.annotation.id
    # Second pass: plain assignments, now that params/annotated locals are known.
    # Two iterations so a `param = param_value` alias resolves regardless of the
    # order ast.walk yields the arg vs the assignment.
    for _ in range(2):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            val = node.value
            t = None
            if isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                t = nondet_ret.get(val.func.id)
            elif isinstance(val, ast.Name):
                t = known.get(val.id)
            elif isinstance(val, ast.Constant):
                t = type(val.value).__name__
            if t:
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        known.setdefault(tgt.id, t)
    return known


def _tautological_type_checks(tree: ast.Module) -> list[str]:
    """`isinstance(x, T)` / `__ESBMC_assume(isinstance(x, T))` where x is already
    declared T proves nothing -- ESBMC-Python gives every variable a fixed static
    type (EXP-02). A type_mismatch slice must model the wrong-type value with a
    differently-typed nondet stand-in and check its shape instead.
    """
    known = _type_map(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "isinstance"
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Name)
        ):
            continue
        name = node.args[0].id
        have = known.get(name)
        if not have:
            continue
        checked: list[str] = []
        if isinstance(node.args[1], ast.Name):
            checked = [node.args[1].id]
        elif isinstance(node.args[1], ast.Tuple):
            checked = [e.id for e in node.args[1].elts if isinstance(e, ast.Name)]
        if have in checked:
            out.append(
                f"isinstance({name}, {have}) is always true here ({name} is declared "
                f"{have}); model the wrong-type case with a differently-typed nondet_*()"
            )
    return list(dict.fromkeys(out))


def _harness_expr_lines(tree: ast.Module) -> list[str]:
    return [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.Return, ast.Assert, ast.AnnAssign))]


def _real_body_lines(real_source: str) -> list[str]:
    try:
        tree = ast.parse(textwrap.dedent(real_source))
    except SyntaxError:
        return []
    return [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.Return, ast.Assert, ast.AnnAssign, ast.If))]


# Ops that carry no arithmetic to preserve -- a type_mismatch / none_misuse
# slice legitimately drops the `isinstance` / `is None` and models the check
# with a differently-typed nondet stand-in instead (see the prompt + the
# tautology guard). The skeleton check does not apply to these.
_NON_ARITHMETIC_OPS = frozenset({"call:isinstance", "is", "is not", "not", "and", "or", "?", ""})


def _arithmetic_survived(harness: ast.Module, expression: str, real_source: str) -> tuple[bool, str]:
    want = _skeleton(expression)
    if want is not None:
        arithmetic = [op for op in want if op not in _NON_ARITHMETIC_OPS]
        if arithmetic:
            harness_ops = _op_multiset(_CollapseAccess().visit(ast.parse(ast.unparse(harness))))
            if _multiset_covered(arithmetic, harness_ops):
                return True, ""
            return False, (
                f"suspect expression operators {arithmetic} not preserved in the harness "
                "(the slice must keep the real arithmetic, only its operands become nondet)"
            )
        # isinstance / is None / boolean-only: nothing arithmetic to preserve;
        # the tautology guard is what keeps this shape honest.
        return True, ""
    # Prose expression: require one real source line to survive near-verbatim.
    real_lines = _real_body_lines(real_source)
    harness_lines = _harness_expr_lines(harness)
    best = max(
        (_token_overlap(h, r) for h in harness_lines for r in real_lines),
        default=0.0,
    )
    if best >= _LINE_OVERLAP_MIN:
        return True, ""
    return False, (
        "no line of the real function survived in the harness "
        f"(best token overlap {best:.2f} < {_LINE_OVERLAP_MIN})"
    )


def check_driver_harness(
    source: str,
    *,
    real_source: str,
    function_name: str,
    expression: str = "",
) -> DriverCheckResult:
    if not source.strip():
        return DriverCheckResult(
            False, VERDICT_INVALID, ["empty harness (the slice method always produces one)"]
        )
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return DriverCheckResult(False, VERDICT_INVALID, [f"does not parse: {exc.msg}"])

    if [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]:
        return DriverCheckResult(False, VERDICT_INVALID, ["harness imports a module (intrinsics are bare)"])

    shadowed = _shadows_intrinsic(tree)
    if shadowed:
        return DriverCheckResult(
            False,
            VERDICT_INVALID,
            [f"redefines ESBMC intrinsic(s): {', '.join(shadowed)} (shadowing makes the run vacuous)"],
        )

    referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    leaked = sorted(referenced & _UNSUPPORTED_NAMES)
    if leaked:
        return DriverCheckResult(
            False, VERDICT_UNSUPPORTED, [f"references unsupported dependency: {', '.join(leaked)}"]
        )

    if any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "__ESBMC_cover"
        for n in ast.walk(tree)
    ):
        return DriverCheckResult(
            False, VERDICT_INVALID, ["uses __ESBMC_cover (driver method checks with plain assert only)"]
        )

    if not _has_module_level_driver(tree):
        return DriverCheckResult(
            False, VERDICT_INVALID, ["no module-level driver (harness must call main() at module level)"]
        )

    if not _result_is_live(tree):
        return DriverCheckResult(
            False, VERDICT_INVALID, ["slice result is not asserted on (it will be sliced away)"]
        )

    if not [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]:
        return DriverCheckResult(False, VERDICT_INVALID, ["harness has no assert (nothing to check)"])

    taut = _tautological_type_checks(tree)
    if taut:
        return DriverCheckResult(False, VERDICT_INVALID, taut)

    survived, why = _arithmetic_survived(tree, expression, real_source)
    if not survived:
        return DriverCheckResult(False, VERDICT_INVALID, [why])

    return DriverCheckResult(True, VERDICT_OK, [])
