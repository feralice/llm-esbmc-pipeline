from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.scan import pipeline as scan_pipeline
from research_pipeline.scan.pipeline import (
    CANDIDATE_NOT_FOUND,
    CONFIRMED_ON_ABSTRACTION,
    INVALID_HARNESS,
    OVER_RESTRICTED,
    SAFE_ON_ABSTRACTION,
    ScanCandidate,
    ScanCaseResult,
    _classify_esbmc,
    _find_unit,
    load_candidates,
    run_pipeline_scan,
)
from research_pipeline.scan.synth import SynthResult

_GOOD_HARNESS = (
    "def core(n: int) -> int:\n"
    "    __ESBMC_assume(n >= 1)\n"
    "    __ESBMC_assume(n <= 100)\n"
    "    assert n != 0, 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
    "    return 10 // n\n"
    "def main() -> None:\n"
    "    core(nondet_int())\n"
    "main()\n"
)


class _FakeSynthesizer:
    def __init__(self, harness: str, model: str = "fake-model"):
        self._harness = harness
        self.model = model

    def synthesize(self, unit, finding, *, use_guards: bool = True, **kwargs) -> SynthResult:
        self.last_use_guards = use_guards
        return SynthResult(
            harness=self._harness,
            raw_response=self._harness,
            model=self.model,
            telemetry={"total_tokens": 123},
        )


def _esbmc(status: str) -> ESBMCDirectResult:
    return ESBMCDirectResult(
        source_file="x.py",
        status=status,
        command=["esbmc"],
        returncode=0,
        summary=status,
        details={"property_kind": "LLM_ESBMC_EXPECTED_PROPERTY"},
    )


def _patch_esbmc(monkeypatch, fn) -> None:
    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", fn)


def _candidate(tmp_path: Path, function: str = "target") -> ScanCandidate:
    f = tmp_path / "mod.py"
    f.write_text("def target(n):\n    return 10 // n\n", encoding="utf-8")
    return ScanCandidate(file=str(f), function=function, category="division_by_zero")


def _run(tmp_path: Path, harness: str, candidate: ScanCandidate, **kw):
    kw.setdefault("synth_retries", 0)
    return run_pipeline_scan(
        [candidate],
        synthesizer=_FakeSynthesizer(harness),
        output_dir=tmp_path / "out",
        **kw,
    )[0]


def test_load_candidates_list_and_wrapper(tmp_path: Path):
    item = {"file": "a.py", "function": "f", "category": "division_by_zero"}
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps([item]), encoding="utf-8")
    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"candidates": [item]}), encoding="utf-8")

    assert load_candidates(bare) == load_candidates(wrapped)
    assert load_candidates(bare)[0].function == "f"


def test_load_candidates_missing_field(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"file": "a.py", "function": "f"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="category"):
        load_candidates(bad)


def test_find_unit_by_name_and_qualname():
    class U:
        def __init__(self, name, qualname):
            self.name = name
            self.qualname = qualname

    units = [U("helper", "helper"), U("run", "Worker.run")]
    assert _find_unit(units, "run").qualname == "Worker.run"
    assert _find_unit(units, "Worker.run").name == "run"
    assert _find_unit(units, "missing") is None


def test_classify_esbmc_mapping():
    assert _classify_esbmc("violation_found") == CONFIRMED_ON_ABSTRACTION
    assert _classify_esbmc("no_violation_found") == SAFE_ON_ABSTRACTION
    assert _classify_esbmc("skipped") == "esbmc_unavailable"
    assert _classify_esbmc("timeout") == "esbmc_inconclusive"
    assert _classify_esbmc("no_vcc_generated") == "no_property"


def test_confirmed_on_abstraction(tmp_path, monkeypatch):
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path))
    assert result.classification == CONFIRMED_ON_ABSTRACTION
    assert result.synth_total_tokens == 123


def test_different_violated_property_is_not_confirmation(tmp_path, monkeypatch):
    def wrong_property(*args, **kwargs):
        result = _esbmc("violation_found")
        result.details["property_kind"] = "Unsupported function 'to_timestamp' is reached"
        return result

    _patch_esbmc(monkeypatch, wrong_property)
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path))
    assert result.classification == INVALID_HARNESS
    assert "different property" in result.compat_reasons[0]


def test_safe_on_abstraction(tmp_path, monkeypatch):
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("no_violation_found"))
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path))
    assert result.classification == SAFE_ON_ABSTRACTION


def test_over_restricted_detected_by_ablation(tmp_path, monkeypatch):
    def fake_esbmc(file_path, **kw):
        text = Path(file_path).read_text(encoding="utf-8")
        if "# [ablated] " not in text:
            return _esbmc("no_violation_found")
        removed_line = text.split("# [ablated] ", 1)[1].splitlines()[0]
        hit = "n >= 1" in removed_line
        return _esbmc("violation_found" if hit else "no_violation_found")

    _patch_esbmc(monkeypatch, fake_esbmc)
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path))
    assert result.classification == OVER_RESTRICTED
    assert any("n >= 1" in a for a in result.masking_assumptions)


def test_invalid_harness_rejected_before_esbmc(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ESBMC must not run on a rejected harness")

    _patch_esbmc(monkeypatch, boom)
    bad_harness = "import os\ndef main():\n    pass\nmain()\n"
    result = _run(tmp_path, bad_harness, _candidate(tmp_path))
    assert result.classification == INVALID_HARNESS


def test_candidate_function_not_found(tmp_path, monkeypatch):
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path, function="nonexistent"))
    assert result.classification == CANDIDATE_NOT_FOUND


def test_no_compat_lets_junk_reach_esbmc(tmp_path, monkeypatch):
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("tool_error"))
    junk = "import os\ndef main():\n    pass\nmain()\n"
    result = _run(tmp_path, junk, _candidate(tmp_path), use_compat=False)
    assert result.classification == "esbmc_inconclusive"
    assert result.compat_verdict == "skipped"


class _RetrySynthesizer:
    """Fails the first N attempts (bad harness), then returns a good one."""

    def __init__(self, fail_times: int):
        self._fail_times = fail_times
        self._calls = 0
        self.model = "retry-model"
        self.feedback = []

    def synthesize(self, unit, finding, *, use_guards: bool = True, **kwargs) -> SynthResult:
        self._calls += 1
        self.feedback.append(kwargs.get("repair_feedback", ""))
        bad = "import os\ndef main():\n    pass\nmain()\n"
        harness = bad if self._calls <= self._fail_times else _GOOD_HARNESS
        return SynthResult(harness=harness, raw_response=harness, model=self.model, telemetry={})


def test_retry_recovers_after_bad_harness(tmp_path, monkeypatch):
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    synthesizer = _RetrySynthesizer(fail_times=1)
    result = run_pipeline_scan(
        [_candidate(tmp_path)],
        synthesizer=synthesizer,
        output_dir=tmp_path / "out",
        synth_retries=2,
    )[0]
    assert result.classification == CONFIRMED_ON_ABSTRACTION
    assert result.attempts == 2
    assert synthesizer.feedback[0] == ""
    assert "imports os" in synthesizer.feedback[1]
    assert len(result.attempt_history) == 2


def test_retry_exhausted_keeps_last_failure_and_full_history(tmp_path, monkeypatch):
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    result = run_pipeline_scan(
        [_candidate(tmp_path)],
        synthesizer=_RetrySynthesizer(fail_times=99),
        output_dir=tmp_path / "out",
        synth_retries=2,
    )[0]
    assert result.classification == INVALID_HARNESS
    assert result.attempts == 3
    assert len(result.attempt_history) == 3


def test_no_ablation_keeps_safe_verdict(tmp_path, monkeypatch):
    def flips_under_ablation(file_path, **kw):
        text = Path(file_path).read_text(encoding="utf-8")
        return _esbmc("violation_found" if "# [ablated] " in text else "no_violation_found")

    _patch_esbmc(monkeypatch, flips_under_ablation)
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path), use_ablation=False)
    assert result.classification == SAFE_ON_ABSTRACTION
    assert result.masking_assumptions == []


def test_completed_result_is_not_synthesized_again(tmp_path, monkeypatch):
    candidate = _candidate(tmp_path)
    completed = ScanCaseResult(
        candidate=candidate,
        classification=CONFIRMED_ON_ABSTRACTION,
        synth_model="old-model",
    )
    synthesizer = _RetrySynthesizer(fail_times=0)
    results = run_pipeline_scan(
        [candidate],
        synthesizer=synthesizer,
        output_dir=tmp_path / "out",
        completed_results={0: completed},
    )
    assert results == [completed]
    assert synthesizer._calls == 0
