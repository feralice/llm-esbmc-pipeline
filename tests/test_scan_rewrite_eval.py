from __future__ import annotations

import json
import pathlib
import shutil

import pytest

from research_pipeline.models import ESBMCResult
from research_pipeline.scan import pipeline as scan_pipeline
from research_pipeline.scan import synth
from research_pipeline.scan.rewrite_eval import evaluate_offline


def _dataset(tmp_path):
    (tmp_path / "detection").mkdir()
    (tmp_path / "bugs").mkdir()
    (tmp_path / "detection" / "a.py").write_text(
        "class Rates:\n    def per(self, total, count):\n        return total // count\n", encoding="utf-8",
    )
    (tmp_path / "detection" / "b.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    (tmp_path / "bugs" / "a.py").write_text("SECRET_HARNESS = 1\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"items": [
        {"id": "a", "detection_file": "detection/a.py", "harness_file": "bugs/a.py",
         "function": "Rates.per", "categories": ["division_by_zero"], "expression": "total // count"},
        {"id": "b", "detection_file": "detection/b.py", "harness_file": "bugs/b.py",
         "function": "f", "categories": ["none_misuse"], "expression": "x"},
    ]}), encoding="utf-8")
    return tmp_path / "manifest.json"


def _timeout_native(*args, **kwargs):
    return ESBMCResult(
        finding_id="x", status="inconclusive", command=[], returncode=None,
        summary="ESBMC excedeu o tempo limite configurado.", time_seconds=1.0,
        details={"reason": "timeout"},
    )


def test_offline_evaluation_never_reads_bug_harness(tmp_path, monkeypatch):
    manifest = _dataset(tmp_path)
    real_read = pathlib.Path.read_text

    def guarded(self, *args, **kwargs):
        assert "bugs" not in self.parts, f"read oracle file {self}"
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", guarded)
    monkeypatch.setattr(scan_pipeline, "run_esbmc_on_function", _timeout_native)
    summary = evaluate_offline(str(manifest), str(tmp_path / "out"), per_case_timeout=5)
    assert summary["cases"] == 2


def test_offline_evaluation_never_calls_llm(tmp_path, monkeypatch):
    manifest = _dataset(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(synth.HarnessSynthesizer, "__init__", lambda *a, **k: pytest.fail("LLM backend built"))
    monkeypatch.setattr(scan_pipeline, "run_esbmc_on_function", _timeout_native)
    evaluate_offline(str(manifest), str(tmp_path / "out"), per_case_timeout=5)


def test_per_case_timeout_recorded_as_inconclusive(tmp_path, monkeypatch):
    manifest = _dataset(tmp_path)
    monkeypatch.setattr(scan_pipeline, "run_esbmc_on_function", _timeout_native)
    evaluate_offline(str(manifest), str(tmp_path / "out"), per_case_timeout=5)
    record = json.loads((tmp_path / "out" / "cases" / "b.json").read_text(encoding="utf-8"))
    assert record["tier"] == "inconclusive"
    assert record["diagnostic"]["kind"] == "timeout"


@pytest.mark.skipif(shutil.which("esbmc") is None, reason="ESBMC binary unavailable")
def test_aggregate_keeps_original_and_rewrite_counts_separate(tmp_path):
    manifest = _dataset(tmp_path)
    summary = evaluate_offline(str(manifest), str(tmp_path / "out"), per_case_timeout=20)
    assert summary["rewrite_stage"] == {"status": "not_run_offline", "eligible_for_rewrite": 1}
    assert summary["by_diagnostic"]["method_entry"] == 1
    assert set(summary["by_tier"]) <= {"confirmed_native", "safe_native", "confirmed_driver",
                                       "safe_driver", "over_restricted", "inconclusive"}
    saved = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert saved["config"]["per_case_timeout"] == 20
    assert len(saved["inputs"]) == 2 and all(len(h) == 64 for h in saved["inputs"].values())
