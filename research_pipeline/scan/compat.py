"""V2 compatibility check for synthesized harnesses.

The LLM (step 3) returns a synthesized harness as text. Before spending an
ESBMC run on it, reject the harnesses ESBMC-Python cannot handle:

- does not parse                         -> invalid_harness
- imports anything                       -> invalid_harness (not self-contained)
- references numpy / pandas / torch / tf -> unsupported_harness
- contains a for/while loop              -> invalid_harness
- no module-level driver (a call or a
  `main()` invoked at module level)      -> invalid_harness

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

VERDICT_OK = "ok"
VERDICT_INVALID = "invalid_harness"
VERDICT_UNSUPPORTED = "unsupported_harness"


@dataclass
class CompatResult:
    """Outcome of the compatibility check for one synthesized harness."""

    ok: bool
    verdict: str            # VERDICT_OK | VERDICT_INVALID | VERDICT_UNSUPPORTED
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


def check_harness(source: str) -> CompatResult:
    """Return a CompatResult for a synthesized harness given as text."""
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

    if any(isinstance(node, (ast.For, ast.AsyncFor, ast.While)) for node in ast.walk(tree)):
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

    return CompatResult(True, VERDICT_OK, [])


def undefined_names(source: str) -> set[str]:
    """Names used but never bound in the harness, minus the allowed intrinsics.

    A non-empty result is a soft warning (the harness may still verify), not a
    hard reject; check_harness() does not use it. Exposed for the scan report.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

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
