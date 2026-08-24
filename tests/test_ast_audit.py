from research_pipeline.ast_utils import explain_ast_mismatch


def test_ast_audit_distinguishes_wrong_category_shape() -> None:
    source = "def sample(items: list[int], i: int) -> int:\n    return items[i]\n"
    audit = explain_ast_mismatch("items[i]", source, "division_by_zero")
    assert audit["code"] == "wrong_node_shape_for_category"
    assert audit["candidates"] == []


def test_ast_audit_reports_line_mismatch_and_candidate_lines() -> None:
    source = """def sample(a: int, b: int) -> int:
    first = a // b
    return a // b
"""
    audit = explain_ast_mismatch("a // b", source, "division_by_zero", 20)
    assert audit["code"] == "line_mismatch"
    assert audit["matching_lines"] == [2, 3]


def test_ast_audit_lists_category_candidates() -> None:
    source = "def sample(a: int, b: int) -> int:\n    return a // b\n"
    audit = explain_ast_mismatch("a / b", source, "division_by_zero")
    assert audit["code"] == "expression_not_found"
    assert audit["candidates"] == ["a // b"]
