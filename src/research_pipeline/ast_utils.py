from __future__ import annotations

import ast
import textwrap

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

_SOURCE_GROUNDED_CATEGORIES = frozenset(
    {
        "none_misuse",
        "type_mismatch",
        "invalid_precondition",
        "variable_misuse",
        "integer_overflow",
    }
)


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
    - V2 semantic categories: exact expression or statement match in executable
      source; this grounds the claim without pretending a node shape proves it.
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

    target_node = _parse_reported_node(expression)
    if target_node is None:
        return False
    target = ast.unparse(target_node)

    # Parse the full function source and walk its executable expression nodes.
    # dedent first: a method's source carries class indentation that ast.parse
    # rejects (IndentationError, a SyntaxError subclass).
    try:
        unit_tree = ast.parse(textwrap.dedent(unit_source))
    except SyntaxError:
        return False

    candidates = _candidate_nodes(unit_tree, category)
    if candidates is None:
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


def explain_ast_mismatch(
    expression: str,
    unit_source: str,
    category: str,
    expected_relative_line: int = 0,
) -> dict[str, object]:
    """Explain why a reported expression did not pass structural grounding."""
    if not expression.strip():
        return {"code": "missing_expression", "candidates": []}
    target_node = _parse_reported_node(expression)
    if target_node is None:
        return {"code": "invalid_expression_syntax", "candidates": []}
    try:
        tree = ast.parse(textwrap.dedent(unit_source))
    except SyntaxError:
        return {"code": "invalid_unit_syntax", "candidates": []}
    candidates = _candidate_nodes(tree, category)
    if candidates is None:
        return {"code": "unsupported_category", "candidates": []}

    candidate_list = list(candidates)
    candidate_text = sorted({ast.unparse(node) for node in candidate_list})
    target = ast.unparse(target_node)
    exact = [node for node in candidate_list if ast.unparse(node) == target]
    if exact and expected_relative_line:
        return {
            "code": "line_mismatch",
            "candidates": candidate_text,
            "matching_lines": sorted({node.lineno for node in exact}),
        }

    if any(ast.unparse(node) == target for node in _executable_nodes(tree)):
        code = "wrong_node_shape_for_category"
    else:
        code = "expression_not_found"
    return {"code": code, "candidates": candidate_text}


def expression_exists_as_statement(
    expression: str, unit_source: str, expected_relative_line: int = 0
) -> bool:
    """Category-agnostic grounding: does `expression` occur as an executable
    expr/stmt node in `unit_source`, at all (line tolerance still applies)?

    For the V2 manifest's outcome categories (assertion_violation,
    incorrect_result) the recorded expression is the buggy statement itself,
    not an assert -- the assert is added later by the synthesized harness, not
    present in the target function. `expression_exists_in_executable_ast`'s
    assertion_violation branch only matches `ast.Assert.test` nodes, which is
    correct for a real LLM-reported assert in scan mode but wrongly flags
    every such manifest label as ungrounded. Use this instead when auditing
    that dataset shape.
    """
    if not expression:
        return False
    target_node = _parse_reported_node(expression)
    if target_node is None:
        return False
    target = ast.unparse(target_node)
    try:
        unit_tree = ast.parse(textwrap.dedent(unit_source))
    except SyntaxError:
        return False
    for node in _executable_nodes(unit_tree):
        try:
            if ast.unparse(node) != target:
                continue
        except Exception:
            continue
        if expected_relative_line and abs(node.lineno - expected_relative_line) > _LINE_TOLERANCE:
            continue
        return True
    return False


def _executable_nodes(tree: ast.AST):
    return (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.expr, ast.stmt))
        and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )


def _candidate_nodes(tree: ast.AST, category: str):
    if category == "division_by_zero":
        return (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.BinOp) and isinstance(node.op, _DIVISION_OPS)
        )
    if category == "out_of_bounds":
        return (node for node in ast.walk(tree) if _is_out_of_bounds_node(node))
    if category == "assertion_violation":
        return (node.test for node in ast.walk(tree) if isinstance(node, ast.Assert))
    if category in _SOURCE_GROUNDED_CATEGORIES:
        return _executable_nodes(tree)
    return None


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
