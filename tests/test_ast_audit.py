from research_pipeline.ast_utils import (
    explain_ast_mismatch,
    expression_exists_as_statement,
)


def test_ast_audit_grounds_expression_without_classifying_category() -> None:
    source = "def sample(items: list[int], i: int) -> int:\n    return items[i]\n"
    assert expression_exists_as_statement("items[i]", source)


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
    assert audit["candidates"] == []


def test_statement_grounding_dedents_method_with_unindented_docstring_text() -> None:
    source = '''    def __init__(self, iterable=None, disable=False):
        """
        Parameters
        ----------
iterable : iterable, optional
        """
        if disable:
            self.iterable = iterable
            return
'''

    assert expression_exists_as_statement("self.iterable = iterable", source)
