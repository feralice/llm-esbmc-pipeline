from __future__ import annotations

import ast
import warnings

"""Small AST helpers used after the LLM response.

This module does not detect or classify bugs by itself. It checks whether an
expression reported by the LLM exists as executable syntax in the function
source. The result is a grounding check: the LLM's claim must point to real
code before it can reach later ESBMC confirmation.
"""

# How many lines away from the LLM-reported line a matching node may still be
# accepted. LLMs commonly report an off-by-a-few line number (blank lines,
# decorators); this keeps grounding meaningful without demanding exact lines.
_LINE_TOLERANCE = 2


def _dedent_unit_source(unit_source: str) -> str:
    """Dedent a function/method slice by its first code line indentation."""
    lines = unit_source.splitlines()
    first = next((line for line in lines if line.strip()), "")
    indent = len(first) - len(first.lstrip())
    if indent <= 0:
        return unit_source
    prefix = " " * indent
    return "\n".join(line.removeprefix(prefix) for line in lines)


def _safe_unparse(node: ast.AST) -> str | None:
    try:
        return ast.unparse(node)
    except (AttributeError, RecursionError, TypeError, ValueError):
        return None


def _parse_source(source: str) -> ast.Module:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(source)


def expression_exists_in_executable_ast(
    expression: str,
    unit_source: str,
    category: str,
    expected_relative_line: int = 0,
) -> bool:
    """Return True when an LLM-reported expression occurs in function source.

    This is an exact normalized-AST text match over executable expression and
    statement nodes. The `category` argument is intentionally ignored: category
    selection is the LLM/dataset hypothesis, while this function only grounds
    the reported evidence in real code. True means "the expression is present
    in the code", not "the category is correct" and not "this is a bug".

    When `expected_relative_line` is given (function-relative, 1-indexed,
    matching `unit_source`'s own line numbering), a matching node also has to
    sit within `_LINE_TOLERANCE` lines of it. Otherwise the same expression
    text occurring elsewhere in the function (a repeated but unrelated
    occurrence) would wrongly ground the LLM's specific claim. A value of 0
    means the LLM gave no line, so the check falls back to matching anywhere
    in the function.
    """
    _ = category
    if not expression:
        return False

    target_node = _parse_reported_node(expression)
    if target_node is None:
        return False
    target = ast.unparse(target_node)

    # Parse the full function source and walk its executable expression nodes.
    # dedent first: a method's source carries class indentation that ast.parse
    # rejects (IndentationError, a SyntaxError subclass).
    try:
        unit_tree = _parse_source(_dedent_unit_source(unit_source))
    except SyntaxError:
        return False

    for node in _executable_nodes(unit_tree):
        # ast.unparse normalizes harmless formatting differences.
        if _safe_unparse(node) != target:
            continue
        if expected_relative_line and abs(node.lineno - expected_relative_line) > _LINE_TOLERANCE:
            continue
        return True
    return False


def explain_ast_mismatch(
    expression: str,
    unit_source: str,
    category: str,
    expected_relative_line: int = 0,
) -> dict[str, object]:
    """Explain why a reported expression did not pass structural grounding."""
    _ = category
    if not expression.strip():
        return {"code": "missing_expression", "candidates": []}
    target_node = _parse_reported_node(expression)
    if target_node is None:
        return {"code": "invalid_expression_syntax", "candidates": []}
    try:
        tree = _parse_source(_dedent_unit_source(unit_source))
    except SyntaxError:
        return {"code": "invalid_unit_syntax", "candidates": []}
    candidate_list = list(_executable_nodes(tree))
    candidate_text: list[str] = []
    target = ast.unparse(target_node)
    exact = [node for node in candidate_list if _safe_unparse(node) == target]
    if exact and expected_relative_line:
        return {
            "code": "line_mismatch",
            "candidates": candidate_text,
            "matching_lines": sorted({node.lineno for node in exact}),
        }

    return {"code": "expression_not_found", "candidates": candidate_text}


def expression_exists_as_statement(
    expression: str, unit_source: str, expected_relative_line: int = 0
) -> bool:
    """Category-agnostic alias for executable AST grounding."""
    return expression_exists_in_executable_ast(
        expression,
        unit_source,
        category="",
        expected_relative_line=expected_relative_line,
    )


def _executable_nodes(tree: ast.AST):
    return (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.expr, ast.stmt))
        and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )


def _parse_reported_node(expression: str) -> ast.AST | None:
    """Parse one reported expression or simple executable statement."""
    try:
        return ast.parse(expression, mode="eval").body
    except SyntaxError:
        pass
    try:
        module = ast.parse(expression)
    except SyntaxError:
        return None
    if len(module.body) != 1:
        return None
    return module.body[0]
