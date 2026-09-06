from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult, ESBMCResult
from research_pipeline.scan import pipeline as scan_pipeline
from research_pipeline.scan.pipeline import (
    CANDIDATE_NOT_FOUND,
    CONFIRMED_NATIVE,
    CONFIRMED_ON_ABSTRACTION,
    CONFIRMED_UNVERIFIED,
    INVALID_HARNESS,
    OVER_RESTRICTED,
    SAFE_NATIVE,
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

_DIFFERENTIAL_OUTCOME_HARNESS = (
    "def core(n: int) -> int:\n"
    "    result: int = 10 // n\n"
    "    expected: int = n - 1\n"
    "    assert result == expected, 'LLM_ESBMC_EXPECTED_PROPERTY'\n"
    "    return result\n"
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


def _native_result(status: str) -> ESBMCResult:
    return ESBMCResult(
        finding_id="native",
        status=status,
        command=["esbmc", "--function"],
        returncode=0,
        summary=status,
    )


def _patch_native(monkeypatch, fn) -> None:
    monkeypatch.setattr(scan_pipeline, "run_esbmc_on_function", fn)


@pytest.fixture(autouse=True)
def _native_skipped_by_default(monkeypatch):
    """Every test in this file exercises the harness-synthesis path unless it
    explicitly opts into a native result via _patch_native -- without this,
    _run_one's native-first check (_try_native) would shell out to a real
    `esbmc` subprocess on every test's throwaway candidate file."""
    _patch_native(monkeypatch, lambda *a, **k: _native_result("skipped"))


def _candidate(tmp_path: Path, function: str = "target") -> ScanCandidate:
    f = tmp_path / "mod.py"
    f.write_text("def target(n):\n    return 10 // n\n", encoding="utf-8")
    return ScanCandidate(file=str(f), function=function, category="division_by_zero")


def _run(tmp_path: Path, harness: str, candidate: ScanCandidate, **kw):
    kw.setdefault("synth_retries", 0)
    # These exercise the scalar-synth / native / ablation / retry logic; the
    # verbatim-driver tier has its own tests (test_scan_driver.py).
    kw.setdefault("use_driver", False)
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


def test_marker_among_multiple_violated_properties_still_confirms(tmp_path, monkeypatch):
    """Regression: --multi-property (added 2026-09-04, EXP-01) can report BOTH
    an __ESBMC_cover reachability goal and the harness's own marked assert as
    separately violated. The marker just needs to be ONE of them.
    """
    def multi_violation(*args, **kwargs):
        result = _esbmc("violation_found")
        result.details["violated_properties"] = [
            "LLM_ESBMC_EXPECTED_PROPERTY", "assertion !(x == 5)",
        ]
        return result

    _patch_esbmc(monkeypatch, multi_violation)
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path))
    assert result.classification == CONFIRMED_ON_ABSTRACTION


def test_only_cover_negation_violated_is_safe_not_invalid(tmp_path, monkeypatch):
    """Regression: before --multi-property, ESBMC could report only the
    __ESBMC_cover's own inverted-assert (proving reachability, as intended)
    while the harness's marked assert genuinely held. That used to be
    misclassified as invalid_harness; it is a real safe result.
    """
    def only_cover(*args, **kwargs):
        result = _esbmc("violation_found")
        result.details["violated_properties"] = ["assertion !(x == 5)"]
        return result

    _patch_esbmc(monkeypatch, only_cover)
    # use_ablation=False: isolate the classification fix from ablation's own
    # (correct) behavior — the mock returns the same fake verdict for every
    # ablated variant too, which ablation would otherwise read as every
    # assumption masking the bug.
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path), use_ablation=False)
    assert result.classification == SAFE_ON_ABSTRACTION
    assert result.compat_reasons == []


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
        use_driver=False,
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
        use_driver=False,
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


def test_native_violation_confirms_without_calling_synthesizer(tmp_path, monkeypatch):
    """ESBMC's own --function/--assign-param-nondet (Flow B) checks the REAL
    source directly -- when it finds a violation, there's no need to spend an
    LLM call synthesizing a harness at all."""
    _patch_native(monkeypatch, lambda *a, **k: _native_result("violation_found"))
    synthesizer = _RetrySynthesizer(fail_times=0)
    result = run_pipeline_scan(
        [_candidate(tmp_path)],
        synthesizer=synthesizer,
        output_dir=tmp_path / "out",
    )[0]
    assert result.classification == CONFIRMED_NATIVE
    assert synthesizer._calls == 0


def test_native_no_violation_is_safe_for_precondition_category(tmp_path, monkeypatch):
    """division_by_zero (and the other 6 precondition-style categories) map
    to one of ESBMC's own automatic checks, so a real no_violation_found
    verdict here is meaningful evidence, not vacuous."""
    _patch_native(monkeypatch, lambda *a, **k: _native_result("no_violation_found"))
    synthesizer = _RetrySynthesizer(fail_times=0)
    candidate = _candidate(tmp_path)
    assert candidate.category == "division_by_zero"
    result = run_pipeline_scan(
        [candidate], synthesizer=synthesizer, output_dir=tmp_path / "out"
    )[0]
    assert result.classification == SAFE_NATIVE
    assert synthesizer._calls == 0


def test_native_no_violation_falls_through_for_outcome_category(tmp_path, monkeypatch):
    """assertion_violation/incorrect_result have no built-in ESBMC property
    encoding the hypothesized "correct" behaviour (no assert exists on the
    real source) -- a no_violation_found verdict here proves nothing (EXP-03,
    docs/experiment_log.md), so the pipeline must fall through to harness
    synthesis instead of trusting it as SAFE_NATIVE."""
    _patch_native(monkeypatch, lambda *a, **k: _native_result("no_violation_found"))
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    candidate = _candidate(tmp_path)
    candidate.category = "assertion_violation"
    result = _run(tmp_path, _GOOD_HARNESS, candidate)
    # Fell through to harness synthesis (not SAFE_NATIVE) and got confirmed
    # there -- then demoted to confirmed_unverified, same policy as any other
    # assertion_violation confirmation (EXP-03), proving native's
    # no_violation_found was correctly NOT trusted as a safe verdict.
    assert result.classification == CONFIRMED_UNVERIFIED


def test_outcome_category_with_differential_assertion_confirms_strongly(tmp_path, monkeypatch):
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    candidate = _candidate(tmp_path)
    candidate.category = "assertion_violation"

    result = _run(tmp_path, _DIFFERENTIAL_OUTCOME_HARNESS, candidate)

    assert result.classification == CONFIRMED_ON_ABSTRACTION
    assert result.compat_reasons == []


def test_native_tool_error_falls_through_to_synthesis(tmp_path, monkeypatch):
    """A real function without full type-hint coverage (the common case for
    unannotated production code) fails Flow B's conversion -- fall through to
    the LLM harness rather than treating that as any kind of verdict."""
    _patch_native(monkeypatch, lambda *a, **k: _native_result("tool_error"))
    _patch_esbmc(monkeypatch, lambda *a, **k: _esbmc("violation_found"))
    result = _run(tmp_path, _GOOD_HARNESS, _candidate(tmp_path))
    assert result.classification == CONFIRMED_ON_ABSTRACTION
