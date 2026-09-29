"""Rewrite stage with a deterministic fake synthesizer; no credentials, no API."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from research_pipeline.models import Finding
from research_pipeline.preprocess import preprocess_file
from research_pipeline.scan import replay_worker
from research_pipeline.scan.capability import CapabilityDiagnostic
from research_pipeline.scan.pipeline import ScanCandidate
from research_pipeline.scan.replay import ReplayOutcome, UnavailableReplayExecutor
from research_pipeline.scan.rewrite import RewriteChange, RewriteProposal
from research_pipeline.scan.rewrite_stage import (
    REWRITE_CONFIRMED_ORIGINAL,
    REWRITE_INCONCLUSIVE,
    REWRITE_REJECTED,
    REWRITE_VIOLATION_EMPIRICAL,
    run_rewrite_stage,
)
from research_pipeline.scan.synth import SynthResult

needs_esbmc = pytest.mark.skipif(shutil.which("esbmc") is None, reason="ESBMC binary unavailable")

FREE_SOURCE = "import os\n\n\ndef ratio(total, count):\n    return total // count\n\n\nprint(os.getcwd())\n"
FREE_MODULE = "def ratio(total, count):\n    return total // count\n"
FREE_REWRITE = "def ratio(total: int, count: int):\n    return total // count\n"
FREE_DRIVER = (
    "def main() -> None:\n    a: int = nondet_int()\n    b: int = nondet_int()\n"
    "    ratio(a, b)\n\n\nmain()\n"
)
ANNOTATE = RewriteChange("def ratio(total, count):", "def ratio(total: int, count: int):", "types")


class _FakeSynth:
    model = "fake-rewriter"

    def __init__(self, *proposals):
        self.proposals = list(proposals)
        self.calls = []

    def synthesize_rewrite(self, unit, finding, diagnostic, *, module_source, repair_feedback="", previous_proposal=""):
        self.calls.append({"module": module_source, "feedback": repair_feedback})
        proposal = self.proposals.pop(0)
        if isinstance(proposal, Exception):
            raise proposal
        return proposal, SynthResult("{}", "{}", self.model, {"total_tokens": 10})


class _TrustedFixtureExecutor:
    """Runs the real worker on host only for these literal fixtures."""

    def __init__(self, directory: Path, allowed: set[str]):
        self.directory = directory
        self.allowed = allowed

    def run(self, source, function, case):
        assert source in self.allowed, "only literal fixtures may run on the host"
        candidate = self.directory / "candidate.py"
        result = self.directory / "result.json"
        candidate.write_text(source, encoding="utf-8")
        subprocess.run(
            [sys.executable, "-I", replay_worker.__file__, str(candidate), function,
             json.dumps(list(case.args)), json.dumps(case.kwargs), str(result)],
            check=True, capture_output=True, text=True, timeout=5,
        )
        return ReplayOutcome(**json.loads(result.read_text(encoding="utf-8")))


def _proposal(rewritten=FREE_REWRITE, driver=FREE_DRIVER, changes=(ANNOTATE,), cases=({"args": [7, 2], "kwargs": {}},)):
    return RewriteProposal(rewritten, driver, tuple(changes), tuple(cases), (), None)


def _setup(tmp_path, source=FREE_SOURCE, function="ratio", expression="total // count"):
    path = tmp_path / "target.py"
    path.write_text(source, encoding="utf-8")
    unit = next(u for u in preprocess_file(path) if u.qualname == function or u.name == function)
    candidate = ScanCandidate(str(path), function, "division_by_zero", expression=expression)
    finding = Finding(
        id="f", stage="scan_candidate", finding_type="suspected_bug", category="division_by_zero",
        title="", explanation="", evidence=[], verifiable=True, confidence="medium",
        metadata={"expression": expression},
    )
    return candidate, unit, finding


def _run(tmp_path, synth, executor, **setup):
    candidate, unit, finding = _setup(tmp_path, **setup)
    return run_rewrite_stage(
        candidate, unit, finding, CapabilityDiagnostic("annotation", "missing type"),
        synthesizer=synth, executor=executor, esbmc_command=None, bound=3,
        timeout_seconds=20, output_dir=tmp_path / "out", finding_id="case_0",
    )


@needs_esbmc
def test_concrete_original_replay_counts_as_confirmed_original(tmp_path):
    executor = _TrustedFixtureExecutor(tmp_path, {FREE_MODULE, FREE_REWRITE})
    result = _run(tmp_path, _FakeSynth(_proposal()), executor)
    assert result.status == REWRITE_CONFIRMED_ORIGINAL, result.reason
    assert result.evidence["witness"]["case"]["args"][1] == 0
    for name in ("original.py", "rewritten.py", "rewrite.diff", "proposal.json"):
        assert (tmp_path / "out" / "case_0" / "round_1" / name).exists()


def test_prompt_gets_context_module_without_side_effects(tmp_path):
    synth = _FakeSynth(_proposal())
    _run(tmp_path, synth, UnavailableReplayExecutor("none"))
    assert synth.calls[0]["module"].strip() == FREE_MODULE.strip()


def test_guard_rejection_skips_esbmc_and_feeds_repair(tmp_path, monkeypatch):
    from research_pipeline.scan import rewrite_stage
    monkeypatch.setattr(rewrite_stage, "run_esbmc_direct", lambda *a, **k: pytest.fail("ESBMC must not run"))
    bad = _proposal(driver="def main() -> None:\n    assert False\n    ratio(1, 0)\n\n\nmain()\n")
    synth = _FakeSynth(bad, bad, bad, bad)
    result = _run(tmp_path, synth, UnavailableReplayExecutor("none"))
    assert result.status == REWRITE_REJECTED
    assert "assert" in synth.calls[1]["feedback"]
    assert len(result.attempts) == 4


def test_malformed_proposal_is_inconclusive_not_rejected(tmp_path):
    synth = _FakeSynth(*[ValueError("rewrite response must be JSON")] * 4)
    result = _run(tmp_path, synth, UnavailableReplayExecutor("none"))
    assert result.status == REWRITE_INCONCLUSIVE
    assert "JSON" in result.reason


@needs_esbmc
def test_missing_replay_runtime_is_inconclusive(tmp_path):
    result = _run(tmp_path, _FakeSynth(_proposal()), UnavailableReplayExecutor("no container"))
    assert result.status == REWRITE_INCONCLUSIVE
    assert result.esbmc_status == "violation_found"
    assert "replay" in result.reason


def test_replay_divergence_rejects_rewrite(tmp_path, monkeypatch):
    from research_pipeline.scan import rewrite_stage
    monkeypatch.setattr(rewrite_stage, "run_esbmc_direct", lambda *a, **k: pytest.fail("ESBMC must not run"))
    changed = "def ratio(total: int, count: int):\n    total = abs(total)\n    return total // count\n"
    change = RewriteChange(
        "def ratio(total, count):\n", "def ratio(total: int, count: int):\n    total = abs(total)\n", "types",
    )
    proposal = _proposal(rewritten=changed, changes=(change,), cases=({"args": [-7, 2], "kwargs": {}},))
    executor = _TrustedFixtureExecutor(tmp_path, {FREE_MODULE, changed})
    synth = _FakeSynth(*[proposal] * 4)
    result = _run(tmp_path, synth, executor)
    assert result.status == REWRITE_REJECTED
    assert result.evidence["replay"]["status"] == "diverged"
    assert "behaves differently" in synth.calls[1]["feedback"]


@needs_esbmc
def test_timeout_stays_inconclusive(tmp_path, monkeypatch):
    from research_pipeline.models import ESBMCDirectResult
    from research_pipeline.scan import rewrite_stage
    monkeypatch.setattr(rewrite_stage, "run_esbmc_direct", lambda path, **k: ESBMCDirectResult(
        source_file=str(path), status="timeout", command=[], returncode=None,
        summary="timeout", time_seconds=20.0,
    ))
    executor = _TrustedFixtureExecutor(tmp_path, {FREE_MODULE, FREE_REWRITE})
    result = _run(tmp_path, _FakeSynth(_proposal()), executor)
    assert result.status == REWRITE_INCONCLUSIVE


METHOD_SOURCE = "class Rates:\n    def per(self, total, count):\n        return total // count\n"
METHOD_REWRITE = "class Rates:\n    def per(self, total: int, count: int):\n        return total // count\n"
METHOD_DRIVER = (
    "def main() -> None:\n    obj = Rates()\n    a: int = nondet_int()\n    b: int = nondet_int()\n"
    "    obj.per(a, b)\n\n\nmain()\n"
)


@needs_esbmc
def test_method_violation_without_object_replay_is_counted_separately(tmp_path):
    proposal = RewriteProposal(
        METHOD_REWRITE, METHOD_DRIVER,
        (RewriteChange("def per(self, total, count):", "def per(self, total: int, count: int):", "types"),),
        ({"args": [7, 2], "kwargs": {}},), (), None,
    )
    executor = _TrustedFixtureExecutor(tmp_path, {METHOD_SOURCE, METHOD_REWRITE})
    result = _run(
        tmp_path, _FakeSynth(proposal), executor,
        source=METHOD_SOURCE, function="Rates.per",
    )
    assert result.status == REWRITE_VIOLATION_EMPIRICAL, result.reason
    assert result.evidence["replay"]["status"] == "matched"


class _PipelineSynth(_FakeSynth):
    """Scalar synthesis always yields an invalid harness; only the rewrite can succeed."""

    def synthesize(self, unit, finding, **kwargs):
        return SynthResult("x = 1\n", "x = 1\n", self.model, {"total_tokens": 1})


def _method_proposal():
    return RewriteProposal(
        METHOD_REWRITE, METHOD_DRIVER,
        (RewriteChange("def per(self, total, count):", "def per(self, total: int, count: int):", "types"),),
        ({"args": [7, 2], "kwargs": {}},), (), None,
    )


def _scan(tmp_path, synth, **kwargs):
    from research_pipeline.scan.pipeline import run_pipeline_scan
    path = tmp_path / "rates.py"
    path.write_text(METHOD_SOURCE, encoding="utf-8")
    candidate = ScanCandidate(str(path), "Rates.per", "division_by_zero", expression="total // count")
    return run_pipeline_scan(
        [candidate], synthesizer=synth, bound=3, timeout_seconds=20, output_dir=tmp_path / "out",
        use_driver=False, synth_retries=0, loop_fallback=False, **kwargs,
    )[0]


@needs_esbmc
def test_rewrite_default_off_makes_no_new_api_call(tmp_path):
    synth = _PipelineSynth()
    result = _scan(tmp_path, synth)
    assert synth.calls == []
    assert result.rewrite_status == ""


@needs_esbmc
def test_original_is_attempted_before_rewrite(tmp_path):
    executor = _TrustedFixtureExecutor(tmp_path, {METHOD_SOURCE, METHOD_REWRITE})
    result = _scan(
        tmp_path, _PipelineSynth(_method_proposal()),
        rewrite_mode="validated", replay_executor=executor,
    )
    assert result.classification == REWRITE_VIOLATION_EMPIRICAL
    assert result.harness_tier == "rewrite"
    assert result.rewrite_evidence["diagnostic"]["kind"] == "method_entry"
    assert result.synth_total_tokens == 10


@needs_esbmc
def test_inconclusive_rewrite_is_recorded_on_the_fallback_result(tmp_path):
    result = _scan(
        tmp_path, _PipelineSynth(_method_proposal()),
        rewrite_mode="validated", replay_executor=UnavailableReplayExecutor("no container"),
    )
    assert result.classification not in {REWRITE_VIOLATION_EMPIRICAL, REWRITE_CONFIRMED_ORIGINAL}
    assert result.rewrite_status == REWRITE_INCONCLUSIVE
    assert "replay" in result.rewrite_evidence["reason"]


@needs_esbmc
def test_empirical_tier_needs_independent_replay_cases(tmp_path):
    partly = "class Rates:\n    def per(self, total, count: int):\n        return total // count\n"
    proposal = RewriteProposal(
        partly, METHOD_DRIVER.replace("a: int = nondet_int()", "a = nondet_int()"),
        (RewriteChange("def per(self, total, count):", "def per(self, total, count: int):", "types"),),
        ({"args": [7, 2], "kwargs": {}},), (), None,
    )
    executor = _TrustedFixtureExecutor(tmp_path, {METHOD_SOURCE, partly})
    result = _run(tmp_path, _FakeSynth(proposal), executor, source=METHOD_SOURCE, function="Rates.per")
    assert result.status == REWRITE_INCONCLUSIVE
    assert "independent" in result.reason


def test_tokens_of_malformed_paid_response_are_counted(tmp_path):
    from research_pipeline.scan.synth import RewriteParseError
    error = RewriteParseError("rewrite response must be JSON", SynthResult("x", "x", "m", {"total_tokens": 42}))
    result = _run(tmp_path, _FakeSynth(*[error] * 4), UnavailableReplayExecutor("none"))
    assert result.tokens == 168


@needs_esbmc
def test_esbmc_conversion_error_is_fed_back_until_it_parses(tmp_path, monkeypatch):
    from research_pipeline.models import ESBMCDirectResult
    from research_pipeline.scan import rewrite_stage
    real = rewrite_stage.run_esbmc_direct
    calls = []

    def flaky(path, **kwargs):
        calls.append(path)
        if len(calls) == 1:
            log = Path(kwargs["output_dir"]) / "first.log"
            log.write_text('ERROR: Object "helper" not found.\n', encoding="utf-8")
            return ESBMCDirectResult(
                source_file=str(path), status="tool_error", command=[], returncode=1,
                summary="erro", raw_log_path=str(log),
            )
        return real(path, **kwargs)

    monkeypatch.setattr(rewrite_stage, "run_esbmc_direct", flaky)
    synth = _FakeSynth(_proposal(), _proposal())
    executor = _TrustedFixtureExecutor(tmp_path, {FREE_MODULE, FREE_REWRITE})
    result = _run(tmp_path, synth, executor)
    assert result.status == REWRITE_CONFIRMED_ORIGINAL, result.reason
    assert 'Object "helper" not found' in synth.calls[1]["feedback"]
    assert result.evidence["rounds"] == 2


def test_rounds_are_capped(tmp_path, monkeypatch):
    from research_pipeline.models import ESBMCDirectResult
    from research_pipeline.scan import rewrite_stage
    monkeypatch.setattr(rewrite_stage, "run_esbmc_direct", lambda path, **k: ESBMCDirectResult(
        source_file=str(path), status="tool_error", command=[], returncode=1, summary="ERROR: unsupported: x",
    ))
    synth = _FakeSynth(*[_proposal()] * 5)
    result = _run(tmp_path, synth, UnavailableReplayExecutor("none"))
    assert result.status == REWRITE_INCONCLUSIVE
    assert len(synth.calls) == 4


STUB_SOURCE = "from proj.utils import helper\n\n\ndef get(items, i):\n    first = items[i]\n    return helper(first)\n"
STUB_REWRITE = (
    "def helper(x: int) -> int:\n    return nondet_int()\n\n\n"
    "def get(items: list[int], i: int) -> int:\n    first = items[i]\n    return helper(first)\n"
)
STUB_DRIVER = (
    "def main() -> None:\n    items: list[int] = [nondet_int(), nondet_int()]\n"
    "    i: int = nondet_int()\n    get(items, i)\n\n\nmain()\n"
)


@needs_esbmc
def test_violation_in_target_with_havoc_stub_is_its_own_tier(tmp_path):
    from research_pipeline.scan.rewrite_stage import REWRITE_CONFIRMED_WITH_STUBS
    path = tmp_path / "target.py"
    path.write_text(STUB_SOURCE, encoding="utf-8")
    unit = next(u for u in preprocess_file(path) if u.name == "get")
    candidate = ScanCandidate(str(path), "get", "out_of_bounds", expression="items[i]")
    finding = Finding(id="f", stage="s", finding_type="suspected_bug", category="out_of_bounds", title="",
                      explanation="", evidence=[], verifiable=True, confidence="medium",
                      metadata={"expression": "items[i]"})
    proposal = RewriteProposal(STUB_REWRITE, STUB_DRIVER, (), ({"args": [[1], 0], "kwargs": {}},), (), None)
    result = run_rewrite_stage(
        candidate, unit, finding, CapabilityDiagnostic("dependency", "Module 'proj' not found"),
        synthesizer=_FakeSynth(proposal), executor=UnavailableReplayExecutor("none"), esbmc_command=None,
        bound=3, timeout_seconds=20, output_dir=tmp_path / "out", finding_id="c",
    )
    assert result.status == REWRITE_CONFIRMED_WITH_STUBS, result.reason
    assert result.evidence["stubs"] == ["helper"]
    assert result.evidence["replay"]["status"] == "skipped_stubbed"
