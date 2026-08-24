from __future__ import annotations

from pathlib import Path

import pytest

from research_pipeline.ast_utils import expression_exists_in_executable_ast
from research_pipeline.evaluator import load_ground_truth_cases
from research_pipeline.llm.categories import FORMAL_CATEGORIES, SUPPORTED_CATEGORIES
from research_pipeline.llm.findings import normalize_findings
from research_pipeline.llm.prompts import load_system_prompt
from research_pipeline.llm.schema import FINDINGS_JSON_SCHEMA
from research_pipeline.models import Finding
from research_pipeline.preprocess import preprocess_file


V2_CATEGORIES = {
    "assertion_violation",
    "division_by_zero",
    "out_of_bounds",
    "none_misuse",
    "type_mismatch",
    "invalid_precondition",
    "variable_misuse",
    "integer_overflow",
}


def _finding(category: str, expression: str) -> Finding:
    return Finding(
        id="candidate",
        stage="llm_analysis",
        finding_type="suspected_bug",
        category=category,
        title="",
        explanation="",
        evidence=[],
        verifiable=True,
        confidence="medium",
        metadata={"expression": expression},
    )


def test_v2_categories_are_aligned_across_prompt_schema_and_registry() -> None:
    enum = set(
        FINDINGS_JSON_SCHEMA["schema"]["properties"]["findings"]["items"]
        ["properties"]["category"]["enum"]
    )
    prompt = load_system_prompt()

    assert V2_CATEGORIES <= FORMAL_CATEGORIES
    assert V2_CATEGORIES <= SUPPORTED_CATEGORIES
    assert V2_CATEGORIES <= enum
    for category in V2_CATEGORIES:
        assert category in prompt


@pytest.mark.parametrize(
    ("category", "expression"),
    [
        ("none_misuse", "len(value)"),
        ("type_mismatch", "value + 1"),
        ("invalid_precondition", "assert size > 0"),
        ("variable_misuse", "picked = stale_value"),
        ("integer_overflow", "value + 1"),
    ],
)
def test_v2_semantic_category_requires_exact_source_grounding(
    tmp_path: Path, category: str, expression: str
) -> None:
    source = """def sample(value: str, size: int, stale_value: int) -> int:
    picked = stale_value
    assert size > 0
    count = len(value)
    return value + 1
"""
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")
    unit = preprocess_file(path)[0]

    normalized = normalize_findings(unit, [_finding(category, expression)])[0]

    assert normalized.finding_type == "suspected_bug"
    assert normalized.verifiable is True


def test_v2_semantic_category_rejects_expression_not_in_source(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text(
        "def sample(value: str) -> int:\n    return len(value)\n", encoding="utf-8"
    )
    unit = preprocess_file(path)[0]

    normalized = normalize_findings(
        unit, [_finding("none_misuse", "value.missing_attribute")]
    )[0]

    assert normalized.finding_type == "llm_false_positive"
    assert normalized.verifiable is False


def test_v1_category_shape_restriction_remains_strict() -> None:
    source = "def sample(items: list[int], i: int) -> int:\n    return items[i]\n"

    assert expression_exists_in_executable_ast(
        "items[i]", source, "out_of_bounds"
    )
    assert not expression_exists_in_executable_ast(
        "items[i]", source, "division_by_zero"
    )


def test_v2_ground_truth_loader_supports_flat_multilabel_layout(tmp_path: Path) -> None:
    bugs = tmp_path / "bugs"
    bugs.mkdir()
    (bugs / "sample.py").write_text(
        "def sample(value: str) -> int:\n    return len(value)\n", encoding="utf-8"
    )
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(
        """{
  "items": [{
    "id": "sample",
    "file": "sample.py",
    "function": "sample",
    "categories": ["none_misuse", "invalid_precondition"],
    "verifiable": true,
    "expression": "len(value)",
    "should_go_to_esbmc": true
  }]
}
""",
        encoding="utf-8",
    )

    cases = load_ground_truth_cases(ground_truth)

    assert cases[0][0] == bugs / "sample.py"
    assert {entry["category"] for entry in cases[0][1]} == {
        "none_misuse",
        "invalid_precondition",
    }
