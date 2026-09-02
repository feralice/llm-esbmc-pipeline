from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    "    return 10 // n\n"
    "def main() -> None:\n"
    "    core(nondet_int())\n"
    "main()\n"
)


class _FakeSynthesizer:
    def __init__(self, harness: str, model: str = "fake-model"):
        self._harness = harness
        self.model = model

    def synthesize(self, unit, finding) -> SynthResult:
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
    )


def _patch_esbmc(monkeypatch, fn) -> None:
    monkeypatch.setattr(scan_pipeline, "run_esbmc_direct", fn)


def _candidate(tmp_path: Path, function: str = "target") -> ScanCandidate:
    f = tmp_path / "mod.py"
    f.write_text("def target(n):\n    return 10 // n\n", encoding="utf-8")
    return ScanCandidate(file=str(f), function=function, category="division_by_zero")


def _run(tmp_path: Path, harness: str, candidate: ScanCandidate):
    return run_pipeline_scan(
        [candidate],
        synthesizer=_FakeSynthesizer(harness),
        output_dir=tmp_path / "out",
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
