"""Tests for `Finding.confidence_source`.

`confidence` alone mixes three unrelated epistemic claims under one string:
the LLM's own guess, ESBMC's formal proof, and the scan pipeline's
pre-verification placeholder. `confidence_source` lets a future aggregation
("accuracy by confidence level") tell them apart instead of crediting a model
guess with the certainty of a formal proof.
"""

from __future__ import annotations

from pathlib import Path

from research_pipeline.evaluator import _flow_a_findings_from_direct
from research_pipeline.llm.findings import finding_from_dict, normalize_findings
from research_pipeline.models import (
    CONFIDENCE_SOURCE_FORMAL_VERIFICATION,
    CONFIDENCE_SOURCE_LLM_SELF_REPORT,
    CONFIDENCE_SOURCE_UNSPECIFIED,
    CodeUnit,
    Finding,
)
from research_pipeline.report import make_missed_bug_result


def _unit() -> CodeUnit:
    return CodeUnit(
        path=Path("m.py"), name="f", qualname="f", source="def f(): pass\n",
        start_line=1, end_line=1, parameters=[], type_hints={},
        operations=[], loops=[], conditionals=[], guards=[], metrics={},
    )


def test_default_is_unspecified_for_legacy_construction():
    finding = Finding(
        id="x", stage="s", finding_type="suspected_bug", category="c",
        title="", explanation="", evidence=[], verifiable=True, confidence="low",
    )
    assert finding.confidence_source == CONFIDENCE_SOURCE_UNSPECIFIED


def test_llm_parsed_finding_is_tagged_as_self_report():
    finding = finding_from_dict({"category": "division_by_zero", "confidence": "high"})
    assert finding.confidence_source == CONFIDENCE_SOURCE_LLM_SELF_REPORT


def test_normalize_findings_preserves_confidence_source_through_both_branches():
    # out_of_scope path
    out_of_scope = finding_from_dict({"category": "not_a_real_category"})
    normalized = normalize_findings(_unit(), [out_of_scope])
    assert normalized[0].confidence_source == CONFIDENCE_SOURCE_LLM_SELF_REPORT

    # supported-category path
    supported = finding_from_dict({"category": "division_by_zero", "verifiable": False})
    normalized = normalize_findings(_unit(), [supported])
    assert normalized[0].confidence_source == CONFIDENCE_SOURCE_LLM_SELF_REPORT


def test_flow_a_finding_is_tagged_as_formal_verification():
    direct = type("D", (), {"status": "violation_found", "details": {"functions": [
        {"status": "violation_found", "name": "f", "property_kind": "array bounds violated"}
    ]}})()
    findings = _flow_a_findings_from_direct(direct)
    assert findings[0].confidence_source == CONFIDENCE_SOURCE_FORMAL_VERIFICATION


def test_missed_bug_synthetic_finding_is_tagged_as_formal_verification():
    direct = type("D", (), {"summary": "violation", "details": {}})()
    result = make_missed_bug_result("f.py", direct, fn_info={"name": "f"})
    assert result.finding.confidence_source == CONFIDENCE_SOURCE_FORMAL_VERIFICATION


