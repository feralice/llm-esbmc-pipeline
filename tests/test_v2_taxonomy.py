from __future__ import annotations

from pathlib import Path

import pytest

from research_pipeline.ast_utils import expression_exists_in_executable_ast
from research_pipeline.evaluator import _flow_a_findings_from_direct, load_ground_truth_cases
from research_pipeline.llm.categories import (
    FORMAL_CATEGORIES,
    SUPPORTED_CATEGORIES,
)
from research_pipeline.llm.findings import normalize_findings
from research_pipeline.llm.prompts import load_system_prompt
from research_pipeline.llm.schema import FINDINGS_JSON_SCHEMA, V2_FINDINGS_JSON_SCHEMA
from research_pipeline.models import ESBMCDirectResult, Finding
from research_pipeline.preprocess import preprocess_file
from research_pipeline.report import UNWINDING_BOUND, _esbmc_result_matches_category

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


def test_v1_categories_are_aligned_across_prompt_schema_and_registry() -> None:
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


@pytest.mark.parametrize("verifiable", [True, False])
def test_v2_normalizer_keeps_the_llm_decision_and_drops_the_category(tmp_path: Path, verifiable: bool) -> None:
    path = tmp_path / "sample.py"
    path.write_text("def sample(value: int) -> int:\n    return value + 1\n", encoding="utf-8")
    unit = preprocess_file(path)[0]
    finding = _finding("unknown", "value + 1")
    finding.verifiable = verifiable

    normalized = normalize_findings(unit, [finding], v2_detection=True)[0]

    assert normalized.finding_type == "suspected_bug"
    assert normalized.verifiable is verifiable
    assert normalized.category == ""


def test_v2_prompt_and_schema_ask_for_no_category() -> None:
    item = V2_FINDINGS_JSON_SCHEMA["schema"]["properties"]["findings"]["items"]
    prompt = load_system_prompt(include_smells=False, v2_detection=True)

    assert "category" not in item["properties"]
    assert set(item["required"]) == set(item["properties"])
    assert list(item["properties"])[-2:] == ["violated_property", "verifiable"]
    assert '"category"' not in prompt
    assert "native_runtime" not in prompt and "8 categorias" not in prompt
    assert "violated_property" in prompt


def test_ast_grounding_does_not_classify_bug_category() -> None:
    source = "def sample(items: list[int], i: int) -> int:\n    return items[i]\n"

    assert expression_exists_in_executable_ast(
        "items[i]", source, "out_of_bounds"
    )
    assert expression_exists_in_executable_ast(
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


def test_v2_ground_truth_loader_prefers_harness_aliases(tmp_path: Path) -> None:
    bugs = tmp_path / "bugs"
    bugs.mkdir()
    (bugs / "sample.py").write_text(
        "def oracle_sample(value: str) -> int:\n    return len(value)\n", encoding="utf-8"
    )
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(
        """{
  "items": [{
    "id": "sample",
    "file": "sample.py",
    "function": "real_sample",
    "expression": "value.strip()",
    "harness_file": "sample.py",
    "harness_function": "oracle_sample",
    "harness_expression": "len(value)",
    "harness_line": 2,
    "categories": ["none_misuse"],
    "verifiable": true,
    "should_go_to_esbmc": true
  }]
}
""",
        encoding="utf-8",
    )

    cases = load_ground_truth_cases(ground_truth)

    assert cases[0][0] == bugs / "sample.py"
    assert cases[0][1][0]["function"] == "oracle_sample"
    assert cases[0][1][0]["expression"] == "len(value)"
    assert cases[0][1][0]["line"] == 2


@pytest.mark.parametrize(
    ("property_kind", "property_text", "expected"),
    [
        ("assertion x != 5", "x != 5", "assertion_violation"),
        ("uncaught exception: ZeroDivisionError", "!(c:@__ESBMC_exc_thrown)", "division_by_zero"),
        ("uncaught exception: IndexError", "!(c:@__ESBMC_exc_thrown)", "out_of_bounds"),
        ("uncaught exception: KeyError", "!(c:@__ESBMC_exc_thrown)", "out_of_bounds"),
        ("uncaught exception: TypeError", "!(c:@__ESBMC_exc_thrown)", "type_mismatch"),
        ("arithmetic overflow on mul", "!overflow(\"*\", x, 2)", "integer_overflow"),
        ("dereference failure: NULL pointer", "", "none_misuse"),
        ("unwinding assertion loop 187", "", UNWINDING_BOUND),
        ("uncaught exception: ValueError", "!(c:@__ESBMC_exc_thrown)", "unknown_esbmc_violation"),
    ],
)
def test_esbmc_python_property_maps_to_category(
    property_kind: str, property_text: str, expected: str
) -> None:
    details = {"property_kind": property_kind, "property_text": property_text}
    assert _esbmc_result_matches_category(details, expected)


def test_unwinding_assertion_is_not_a_flow_a_finding() -> None:
    direct = ESBMCDirectResult(
        source_file="x.py",
        status="violation_found",
        command=["esbmc"],
        returncode=1,
        summary="v",
        details={
            "functions": [
                {"name": "f", "status": "violation_found",
                 "property_kind": "unwinding assertion loop 3"},
                {"name": "g", "status": "violation_found",
                 "property_kind": "uncaught exception: IndexError"},
            ]
        },
    )
    findings = _flow_a_findings_from_direct(direct)
    assert [(f.metadata["function"], f.category) for f in findings] == [("g", "out_of_bounds")]


@pytest.mark.parametrize(("raw", "expected"), [(True, True), (False, False), ("false", False), ("True", True), (1, False)])
def test_verifiable_must_be_a_real_true_to_reach_esbmc(raw, expected) -> None:
    from research_pipeline.llm.findings import finding_from_dict

    assert finding_from_dict({"finding_type": "suspected_bug", "verifiable": raw}).verifiable is expected
