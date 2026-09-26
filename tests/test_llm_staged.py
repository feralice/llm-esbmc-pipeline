from __future__ import annotations

import pytest

from research_pipeline.llm.staged import (
    CLASSIFICATION_JSON_SCHEMA,
    LOCALIZATION_JSON_SCHEMA,
    LocationCandidate,
    ClassificationResult,
    TwoStageAnalyzer,
    build_stage_user_prompt,
    parse_classification_payload,
    parse_localization_payload,
)
from research_pipeline.models import CodeUnit


def _unit(source: str = "def f(x: int) -> int:\n    return 1 // x\n") -> CodeUnit:
    return CodeUnit(
        path=None,
        name="f",
        qualname="f",
        source=source,
        start_line=1,
        end_line=source.count("\n"),
        parameters=["x"],
        type_hints={"x": "int"},
        operations=[],
        loops=[],
        conditionals=[],
        guards=[],
        metrics={"line_count": 2, "parameter_count": 1},
    )


def test_stage_schemas_have_distinct_contracts_without_fake_category():
    localization_properties = LOCALIZATION_JSON_SCHEMA["schema"]["properties"]
    classification_properties = CLASSIFICATION_JSON_SCHEMA["schema"]["properties"]

    assert "candidates" in localization_properties
    assert "findings" not in localization_properties
    assert "findings" in classification_properties
    categories = classification_properties["findings"]["items"]["properties"]["category"]["enum"]
    assert set(categories) == {
        "assertion_violation", "division_by_zero", "out_of_bounds", "none_misuse",
        "type_mismatch", "invalid_precondition", "variable_misuse", "integer_overflow",
    }
    assert "unclassified" not in categories


def test_localization_prompt_has_untrusted_markers_and_no_ground_truth():
    prompt = build_stage_user_prompt(_unit(), stage="localize")

    assert "UNTRUSTED_PYTHON" in prompt
    assert "UNTRUSTED_METADATA" in prompt
    assert "ground truth" not in prompt.lower()
    assert "categoria" not in prompt.lower()


def test_stage_prompts_share_truncation_marker():
    long_source = "def f(x: int) -> int:\n" + "    x = x + 1\n" * 5000
    unit = _unit(long_source)

    for stage in ("localize", "classify"):
        prompt = build_stage_user_prompt(unit, stage=stage, candidates=[])
        assert "PROMPT_CONTEXT_TRUNCATED" in prompt


def test_parse_localization_payload_returns_auditable_candidates():
    candidates = parse_localization_payload({
        "candidates": [{
            "candidate_id": "c1",
            "expression": "1 // x",
            "line": 2,
            "operands": ["x"],
            "guard_evidence": "none",
            "missing_guard": "x != 0",
            "context_needed": [],
            "explanation": "x is unconstrained before division",
        }]
    })

    assert candidates == [LocationCandidate(
        candidate_id="c1",
        expression="1 // x",
        line=2,
        operands=["x"],
        guard_evidence="none",
        missing_guard="x != 0",
        context_needed=[],
        explanation="x is unconstrained before division",
    )]


def test_parse_classification_rejects_unknown_candidate_or_category():
    candidates = [LocationCandidate("c1", "1 // x", 2, ["x"], "none", "x != 0", [], "")]

    with pytest.raises(ValueError, match="candidate_id"):
        parse_classification_payload({
            "findings": [{"candidate_id": "missing", "category": "division_by_zero", "verifiable": True, "explanation": ""}]
        }, candidates)

    with pytest.raises(ValueError, match="categoria"):
        parse_classification_payload({
            "findings": [{"candidate_id": "c1", "category": "clean", "verifiable": True, "explanation": ""}]
        }, candidates)


class _StagedBackend:
    model = "fake"

    def __init__(self, locations, classifications):
        self.locations = locations
        self.classifications = classifications
        self.calls = []

    def analyze_stage(self, unit, *, stage, candidates=None):
        self.calls.append((stage, candidates))
        if stage == "localize":
            return self.locations
        return self.classifications


def test_two_stage_analyzer_calls_localization_then_classification():
    location = LocationCandidate("c1", "1 // x", 2, ["x"], "none", "x != 0", [], "")
    classification = ClassificationResult("c1", "division_by_zero", True, "x may be zero")
    backend = _StagedBackend([location], [classification])
    analyzer = TwoStageAnalyzer(backend)

    findings = analyzer.analyze(_unit())

    assert [call[0] for call in backend.calls] == ["localize", "classify"]
    assert findings[0].category == "division_by_zero"
    assert findings[0].metadata["two_stage_candidate_id"] == "c1"
    assert [event["analysis_stage"] for event in analyzer.telemetry_events] == [
        "localize", "classify",
    ]


def test_two_stage_analyzer_skips_classification_when_localization_is_empty():
    backend = _StagedBackend([], [])

    assert TwoStageAnalyzer(backend).analyze(_unit()) == []
    assert [call[0] for call in backend.calls] == ["localize"]
