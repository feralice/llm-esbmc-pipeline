"""Regression test for the finding-id collision across functions.

system_prompt.txt never asks the LLM for an `id`, so every raw finding
dict lacks one. `finding_from_dict` used to default the missing id to the
literal string "unknown" -- a non-blank placeholder that `_unique_finding_id`
then accepted as a genuine id instead of falling back to its qualname-scoped
default. Two different functions in the same file, each with exactly one bug
finding (the common case), both produced id "unknown". That id is used
verbatim as part of the ESBMC log file name in
`verification.esbmc_runner.run_esbmc_on_function`, so the second function's
verification log silently overwrote the first's.
"""

from __future__ import annotations

from pathlib import Path

from research_pipeline.llm.findings import finding_from_dict, normalize_findings
from research_pipeline.models import CodeUnit


def _unit(qualname: str) -> CodeUnit:
    return CodeUnit(
        path=Path("m.py"), name=qualname, qualname=qualname, source="def f(): pass\n",
        start_line=1, end_line=1, parameters=[], type_hints={},
        operations=[], loops=[], conditionals=[], guards=[], metrics={},
    )


def test_raw_finding_without_id_defaults_to_blank_not_a_placeholder():
    finding = finding_from_dict({"category": "division_by_zero"})
    assert finding.id == ""


def test_two_functions_each_with_one_unnamed_finding_get_distinct_ids():
    # This is the exact shape that used to collide: one finding per function,
    # neither carrying an LLM-supplied id.
    raw = {"category": "division_by_zero", "verifiable": False}
    finding_a = normalize_findings(_unit("mod.divide"), [finding_from_dict(raw)])[0]
    finding_b = normalize_findings(_unit("mod.subtract"), [finding_from_dict(raw)])[0]
    assert finding_a.id != finding_b.id
    assert finding_a.id != "unknown"
    assert finding_b.id != "unknown"


def test_multiple_unnamed_findings_within_one_function_stay_unique():
    raw = {"category": "division_by_zero", "verifiable": False}
    unit = _unit("mod.f")
    findings = normalize_findings(unit, [finding_from_dict(raw), finding_from_dict(raw)])
    assert findings[0].id != findings[1].id
