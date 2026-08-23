from __future__ import annotations

import ast


"""Small AST helpers used after the LLM response.

This module does not detect bugs by itself. It only checks whether an
expression reported by the LLM exists as executable syntax in the function
source, restricted to the node shape that actually matters for the reported
bug category. The result is used as a structural sanity check before a
finding is treated as verifiable.
"""


_DIVISION_OPS = (ast.Div, ast.FloorDiv, ast.Mod)

# How many lines away from the LLM-reported line a matching node may still be
# accepted. LLMs commonly report an off-by-a-few line number (blank lines,
# decorators); this keeps grounding meaningful without demanding exact lines.
_LINE_TOLERANCE = 2

# Method calls that index/mutate a sequence by position without going through
# a Subscript node (e.g. `lst.pop(i)`, `lst.insert(i, x)`). Kept narrow: only
# methods whose argument is itself a position, so a match here is still
# evidence of an out-of-bounds-shaped operation.
_OOB_METHOD_NAMES = frozenset({"pop", "insert"})


def _is_out_of_bounds_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _OOB_METHOD_NAMES
    )


def expression_exists_in_executable_ast(
    expression: str,
    unit_source: str,
    category: str,
    expected_relative_line: int = 0,
) -> bool:
    """Return True when an LLM-reported expression occurs in function source.

    This is an exact normalized-AST text match, restricted to node types that
    are actually meaningful for `category`. True means "the expression is
    present in the code as this kind of operation", not "the expression is
    definitely a bug".

    - division_by_zero: only BinOp nodes using Div/FloorDiv/Mod count.
    - out_of_bounds: only Subscript nodes, or calls to `.pop`/`.insert`.
    - assertion_violation: only the `test` of a real `ast.Assert` counts
      (never the full assert statement).
    - any other category: never matches.

    When `expected_relative_line` is given (function-relative, 1-indexed,
    matching `unit_source`'s own line numbering), a matching node also has to
    sit within `_LINE_TOLERANCE` lines of it. Otherwise the same expression
    text occurring elsewhere in the function (a repeated but unrelated
    occurrence) would wrongly ground the LLM's specific claim. A value of 0
    means the LLM gave no line, so the check falls back to matching anywhere
    in the function.
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

    if category == "division_by_zero":
        candidates = (
            node
            for node in ast.walk(unit_tree)
            if isinstance(node, ast.BinOp) and isinstance(node.op, _DIVISION_OPS)
        )
    elif category == "out_of_bounds":
        candidates = (node for node in ast.walk(unit_tree) if _is_out_of_bounds_node(node))
    elif category == "assertion_violation":
        candidates = (node.test for node in ast.walk(unit_tree) if isinstance(node, ast.Assert))
    else:
        return False

    for node in candidates:
        try:
            # ast.unparse normalizes harmless formatting differences.
            if ast.unparse(node) != target:
                continue
        except Exception:
            continue
        if expected_relative_line and abs(node.lineno - expected_relative_line) > _LINE_TOLERANCE:
            continue
        return True
    return False
