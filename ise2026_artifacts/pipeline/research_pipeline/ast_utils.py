from __future__ import annotations

import ast


"""Small AST helpers used after the LLM response.

This module does not detect bugs by itself. It only checks whether an
expression reported by the LLM exists as executable syntax in the function
source. The result is used as a structural sanity check before a finding is
treated as verifiable.
"""


# Node kinds that can represent executable expressions worth matching against
# an LLM-reported expression.
_EXECUTABLE_NODE_TYPES = (ast.Call, ast.Subscript, ast.BinOp, ast.Compare, ast.Attribute)


def expression_exists_in_executable_ast(expression: str, unit_source: str) -> bool:
    """Return True when an LLM-reported expression occurs in function source.

    This is an exact normalized-AST text match. True means "the expression is
    present in the code", not "the expression is definitely a bug".
    """
    if not expression:
        return False

    # Parse the LLM expression in eval mode so only expression syntax is valid.
    try:
        target = ast.unparse(ast.parse(expression, mode="eval").body)
    except SyntaxError:
        return False

    # Parse the full function source and walk its executable expression nodes.
    try:
        unit_tree = ast.parse(unit_source)
    except SyntaxError:
        return False

    for node in ast.walk(unit_tree):
        if isinstance(node, _EXECUTABLE_NODE_TYPES):
            try:
                # ast.unparse normalizes harmless formatting differences.
                if ast.unparse(node) == target:
                    return True
            except Exception:
                continue
    return False
