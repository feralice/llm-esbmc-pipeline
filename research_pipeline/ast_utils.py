from __future__ import annotations

import ast


_EXECUTABLE_NODE_TYPES = (ast.Call, ast.Subscript, ast.BinOp, ast.Compare, ast.Attribute)


def expression_exists_in_executable_ast(expression: str, unit_source: str) -> bool:
    """Return True if expression matches an executable AST node in function source."""
    if not expression:
        return False
    try:
        target = ast.unparse(ast.parse(expression, mode="eval").body)
    except SyntaxError:
        return False
    try:
        unit_tree = ast.parse(unit_source)
    except SyntaxError:
        return False
    for node in ast.walk(unit_tree):
        if isinstance(node, _EXECUTABLE_NODE_TYPES):
            try:
                if ast.unparse(node) == target:
                    return True
            except Exception:
                continue
    return False
