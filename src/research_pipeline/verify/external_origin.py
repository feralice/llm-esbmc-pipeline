"""Tell a failure that comes from a stubbed library response apart from one in the project's own code."""

from __future__ import annotations

import ast

from .grounding import Grounded

_SUBSCRIPT_ERRORS = frozenset({"KeyError"})


def _squash(text: str) -> str:
    return "".join(text.split())


def _call_name(node: ast.Call) -> str:
    parts, func = [], node.func
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return ".".join(reversed(parts))


def _is_stubbed(name: str, grounded: Grounded) -> bool:
    root, _, member = name.partition(".")
    if name in grounded.stub_keys or name in grounded.externals.calls:
        return True
    return bool(member) and grounded.object_members.get(root, {}).get(member) is not None


def stubbed_response_origin(source: str, grounded: Grounded, exception: str) -> str:
    """The call whose stubbed result the suspect expression subscripts, or "" when it is not one."""
    if exception not in _SUBSCRIPT_ERRORS:
        return ""
    function = next((n for n in ast.walk(ast.parse(source))
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.name == grounded.method_name), None)
    if function is None:
        return ""
    origins: dict[str, str] = {}
    for node in ast.walk(function):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and _is_stubbed(_call_name(node.value), grounded)):
            origins[node.targets[0].id] = _call_name(node.value)
    suspect = _squash(grounded.hypothesis.suspect_expression)
    for node in ast.walk(function):
        if not isinstance(node, ast.Subscript):
            continue
        root = node.value
        while isinstance(root, ast.Subscript):
            root = root.value
        if isinstance(root, ast.Name) and root.id in origins and (
                node.lineno == grounded.hypothesis.line or _squash(ast.unparse(node)) in suspect):
            return origins[root.id]
    return ""
