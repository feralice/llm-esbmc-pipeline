"""Which V2 prompt variants a function gets, from its AST, before detection (routing_v1).

The first row that matches wins, in this order; a function that matches none gets the default, the variants of
the frozen runs. The table is fixed in code and versioned; it never looks at results.
"""

from __future__ import annotations

import ast

ROUTING_VERSION = "routing_v1"
DEFAULT_VARIANTS = ("A1", "A2")

_ARITHMETIC = (ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.LShift, ast.RShift)
_LENGTH_OR_NEXT = frozenset({"len", "next"})


def _parameters(function: ast.AST) -> set[str]:
    args = function.args
    return {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}


def _arithmetic(function: ast.AST, _params: set[str]) -> bool:
    return any(isinstance(node, ast.BinOp) and isinstance(node.op, _ARITHMETIC) for node in ast.walk(function))


def _access(function: ast.AST, params: set[str]) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Subscript):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _LENGTH_OR_NEXT:
            return True
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in params:
            return True
    return False


def _state(function: ast.AST, _params: set[str]) -> bool:
    stores: dict[str, int] = {}
    for node in ast.walk(function):
        if isinstance(node, (ast.Assert, ast.Raise)):
            return True
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
    return any(count > 1 for count in stores.values())


ROUTES: tuple[tuple[tuple[str, ...], object], ...] = (
    (("A2", "A16"), _arithmetic),
    (("A2", "A12"), _access),
    (("A2", "A20"), _state),
)


def route_variants(source: str) -> tuple[str, ...]:
    """Variants for one function's source; the default when the source does not parse or matches no row."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return DEFAULT_VARIANTS
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not functions:
        return DEFAULT_VARIANTS
    function = functions[0]
    params = _parameters(function)
    for variants, matches in ROUTES:
        if matches(function, params):
            return variants
    return DEFAULT_VARIANTS
