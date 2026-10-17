"""Branches Python 3 never runs, folded before slicing so their names pull in no dependencies.

``TYPE_CHECKING`` (imported from ``typing``) is false at run time, and ``sys.version_info`` is the replay
interpreter's. A decided ``if``/``elif`` test becomes ``True``/``False``, its dead arm becomes ``pass``,
and every line keeps its number. A fold that would not parse is not applied.
"""

from __future__ import annotations

import ast
import sys

_TYPING = ("typing", "typing_extensions")
_COMPARE = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b,
            ast.GtE: lambda a, b: a >= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


class _Names:
    """Which module-level names are the real constants: imported once and never rebound."""

    def __init__(self, tree: ast.Module):
        bound: dict[str, int] = {}
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                names = [node.id]
            elif isinstance(node, ast.arg):
                names = [node.arg]
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [(a.asname or a.name).split(".")[0] for a in node.names]
            for name in names:
                bound[name] = bound.get(name, 0) + 1
        imported_from = {(a.asname or a.name): (n.module or "") for n in tree.body if isinstance(n, ast.ImportFrom)
                         for a in n.names}
        modules = {(a.asname or a.name): a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
        once = {name for name, count in bound.items() if count == 1}
        self.type_checking = "TYPE_CHECKING" in once and imported_from.get("TYPE_CHECKING") in _TYPING
        self.typing = {alias for alias, module in modules.items() if module in _TYPING and alias in once}
        self.sys = "sys" in once and modules.get("sys") == "sys"


def _is_sys_version(node: ast.expr, names: _Names) -> bool:
    return (names.sys and isinstance(node, ast.Attribute) and node.attr == "version_info"
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def _version_value(node: ast.expr, names: _Names):
    """The value a version expression has here, or None when it is not one."""
    version = tuple(sys.version_info)
    if _is_sys_version(node, names):
        return version
    if isinstance(node, ast.Attribute) and _is_sys_version(node.value, names) and node.attr in ("major", "minor"):
        return version[0 if node.attr == "major" else 1]
    if isinstance(node, ast.Subscript) and _is_sys_version(node.value, names):
        index = node.slice
        if isinstance(index, ast.Constant) and isinstance(index.value, int) and 0 <= index.value < 3:
            return version[index.value]
        if (isinstance(index, ast.Slice) and index.lower is None and index.step is None
                and isinstance(index.upper, ast.Constant) and isinstance(index.upper.value, int)):
            return version[:index.upper.value]
    return None


def _literal(node: ast.expr):
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None
    if isinstance(value, int) or (isinstance(value, tuple) and all(isinstance(v, int) for v in value)):
        return value
    return None


def _pure(node: ast.expr) -> bool:
    """Evaluating it runs no user code: no call, attribute (a property) or subscript."""
    return all(isinstance(n, (ast.Name, ast.Constant, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.Load, ast.Tuple,
                              ast.cmpop, ast.boolop, ast.unaryop)) for n in ast.walk(node))


def _decide(node: ast.expr, names: _Names) -> bool | None:
    if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING" and names.type_checking:
        return False
    if (isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING" and isinstance(node.value, ast.Name)
            and node.value.id in names.typing):
        return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _decide(node.operand, names)
        return None if inner is None else not inner
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARE:
        left, right = _version_value(node.left, names), _literal(node.comparators[0])
        if left is not None and right is not None and isinstance(left, tuple) == isinstance(right, tuple):
            return _COMPARE[type(node.ops[0])](left, right)
        return None
    if isinstance(node, ast.BoolOp):
        # An operand decides the whole only when everything evaluated before it runs no user code.
        stop = isinstance(node.op, ast.Or)
        results = [_decide(value, names) for value in node.values]
        for index, result in enumerate(results):
            if result is stop and all(_pure(v) for v in node.values[:index]):
                return stop
        return (not stop) if all(r is (not stop) for r in results) else None
    return None


def _first_line(node: ast.stmt) -> int:
    return min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])


def _blank_block(lines: list[bytes], body: list[ast.stmt]) -> tuple[int, int]:
    first, last = _first_line(body[0]) - 1, body[-1].end_lineno - 1
    indent = lines[first][:len(lines[first]) - len(lines[first].lstrip())]
    lines[first] = indent + b"pass"
    for k in range(first + 1, last + 1):
        lines[k] = b""
    return first + 1, last + 1


def fold_dead_guards(source: str) -> tuple[str, list[str]]:
    tree = ast.parse(source)
    names = _Names(tree)
    lines = [line.encode("utf-8") for line in source.splitlines()]  # AST offsets count UTF-8 bytes
    blanked: list[tuple[int, int]] = []
    folded = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or any(a <= node.lineno <= b for a, b in blanked):
            continue
        result = _decide(node.test, names)
        if result is None:
            continue
        test = node.test
        row, end = test.lineno - 1, test.end_lineno - 1
        if row != end and lines[row][test.col_offset - 1:test.col_offset] != b"(":
            continue  # a test continued with backslashes cannot lose its middle lines
        head, tail, word = lines[row][:test.col_offset], lines[end][test.end_col_offset:], str(result).encode()
        if row == end:
            lines[row] = head + word + tail
        else:
            lines[row] = head + word
            for k in range(row + 1, end):
                lines[k] = b""
            lines[end] = tail
        if result is False and _first_line(node.body[0]) > test.end_lineno:
            blanked.append(_blank_block(lines, node.body))
        is_elif = (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
                   and lines[node.orelse[0].lineno - 1].lstrip().startswith(b"elif"))
        if result is True and node.orelse and not is_elif:
            blanked.append(_blank_block(lines, node.orelse))
        folded += 1
    if not folded:
        return source, []
    out = "\n".join(line.decode("utf-8") for line in lines) + "\n"
    try:
        ast.parse(out)
    except SyntaxError:
        return source, []
    return out, [f"dead_guards_folded:{folded}"]
