from __future__ import annotations

import json
from pathlib import Path

import main
from research_pipeline.models import ESBMCDirectResult, Finding
from research_pipeline.scan.synth import SynthResult
from research_pipeline.verify import loop
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.loop import verification_source
from research_pipeline.verify.replay import ReplayVerdict


class _Analyzer:
    def analyze(self, unit):
        return [Finding(id="f1", stage="llm_analysis", finding_type="suspected_bug", category="division_by_zero",
                        title="", explanation="y may be zero", evidence=[], verifiable=True, confidence="high",
                        metadata={"expression": "helper(x) // y"})]


class _SpecLLM:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]
        self.telemetry_events = []

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        return SynthResult(harness=json.dumps({"params": {"x": "int", "y": "int"}}), raw_response="",
                           model=self.model, telemetry={"total_tokens": 5})


def _esbmc(path, **kwargs):
    return ESBMCDirectResult(source_file=str(path), status="violation_found", command=["esbmc"], returncode=1,
                             summary="", details={"violated_properties": ["uncaught exception: ZeroDivisionError"],
                                                  "violated_files": [""]})


def test_verify_engine_verifies_detected_hypotheses_on_the_full_source(tmp_path: Path, monkeypatch) -> None:
    detection = tmp_path / "detection" / "sample.py"
    full = tmp_path / "full" / "sample.py"
    detection.parent.mkdir()
    full.parent.mkdir()
    detection.write_text("def divide(x, y):\n    return helper(x) // y\n", encoding="utf-8")
    full.write_text("def helper(v):\n    return v\n\n\ndef divide(x, y):\n    return helper(x) // y\n",
                    encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "HarnessSynthesizer", _SpecLLM)
    monkeypatch.setattr(loop, "run_esbmc_direct", _esbmc)
    seen = {}

    def replay(program, function, **_):
        seen["source"] = program.source
        return ReplayVerdict("reproduced", "ZeroDivisionError", 5)

    monkeypatch.setattr(loop, "concrete_replay", replay)
    out = tmp_path / "out"
    args = main.build_parser().parse_args([
        "--mode", "hybrid", "--input", str(detection), "--output-dir", str(out),
        "--v2-engine", "verify", "--verification-sources", str(full.parent), "--esbmc-command", "esbmc",
    ])

    assert main.mode_v2(args) == 0
    report = json.loads((out / "v2_verify_report.json").read_text(encoding="utf-8"))
    assert report["verification"]["by_verdict"]["CONFIRMED"] == 1
    assert report["results"][0]["hypothesis"]["file"] == str(detection)
    assert report["config"]["v2_engine"] == "verify"
    assert "def helper(v):" in seen["source"]


def test_verification_source_falls_back_to_the_detection_file(tmp_path: Path) -> None:
    detection = tmp_path / "a.py"
    detection.write_text("", encoding="utf-8")
    h = BugHypothesis(str(detection), "f", "x")
    assert verification_source(h, tmp_path / "missing") == detection
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "a.py").write_text("", encoding="utf-8")
    assert verification_source(h, tmp_path / "full") == tmp_path / "full" / "a.py"


def test_strict_verification_sources_skip_cases_without_a_file(tmp_path: Path) -> None:
    from research_pipeline.verify.loop import run_verify

    (tmp_path / "a.py").write_text("def f(a):\n    return 1 // a\n", encoding="utf-8")
    (tmp_path / "fixed").mkdir()
    results = run_verify([BugHypothesis(str(tmp_path / "a.py"), "f", "1 // a")], llm=None, output_dir=tmp_path,
                         verification_sources=tmp_path / "fixed", strict_sources=True)
    assert results[0]["verdict"] == "NO_SOURCE"
