from __future__ import annotations

import json
from pathlib import Path

import pytest

import main
from research_pipeline.models import Finding


class _Analyzer:
    calls = 0

    def analyze(self, unit):
        type(self).calls += 1
        return [
            Finding(
                id="f1",
                stage="llm_analysis",
                finding_type="suspected_bug",
                category="division_by_zero",
                title="",
                explanation="denominator may be zero",
                evidence=[],
                verifiable=True,
                confidence="high",
                metadata={"expression": "x // y"},
            )
        ]


class _Synthesizer:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]


class _AnalyzerWithSmell:
    def analyze(self, unit):
        return [
            Finding(
                id="smell",
                stage="llm_analysis",
                finding_type="smell_heuristic",
                category="long_method",
                title="",
                explanation="too long",
                evidence=[],
                verifiable=False,
                confidence="high",
                metadata={},
            ),
            Finding(
                id="wrong-result-bug",
                stage="llm_analysis",
                finding_type="suspected_bug",
                category="",
                title="",
                explanation="returns the wrong value, nothing raises",
                evidence=[],
                verifiable=False,
                confidence="high",
                metadata={"expression": "f(...)"},
            ),
        ]


def test_v2_forwards_only_findings_the_llm_marks_verifiable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(value: int) -> int:\n    return value\n", encoding="utf-8")
    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _AnalyzerWithSmell())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", lambda hypotheses, **kwargs: captured.setdefault("candidates", hypotheses) or [])

    args = main.build_parser().parse_args(["--mode", "hybrid", "--input", str(source), "--output-dir", str(tmp_path / "out")])

    assert main.mode_v2(args) == 0
    assert captured["candidates"] == []


def test_v2_detects_before_synthesizing(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    captured = {}

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)

    def fake_pipeline(candidates, **kwargs):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr(main, "run_verify", fake_pipeline)
    args = main.build_parser().parse_args(
        [
            "--mode", "hybrid", "--input", str(source),
            "--output-dir", str(tmp_path / "out"),
        ]
    )

    assert main.mode_v2(args) == 0
    assert len(captured["candidates"]) == 1
    candidate = captured["candidates"][0]
    assert candidate.function == "divide"
    assert candidate.category == ""  # V2 detection gives no category
    assert candidate.suspect_expression == "x // y"


def test_v2_resume_does_not_repeat_completed_detection(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    _Analyzer.calls = 0
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", lambda hypotheses, **kwargs: [])
    parser = main.build_parser()
    base = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(output)]

    assert main.mode_v2(parser.parse_args(base)) == 0
    assert _Analyzer.calls == 1
    assert main.mode_v2(parser.parse_args([*base, "--resume"])) == 0
    assert _Analyzer.calls == 1


def test_v2_marks_checkpoint_interrupted_when_synthesis_is_cancelled(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)

    def interrupted_pipeline(candidates, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "run_verify", interrupted_pipeline)
    args = main.build_parser().parse_args(
        ["--mode", "hybrid", "--input", str(source), "--output-dir", str(output)]
    )

    assert main.mode_v2(args) == 2
    checkpoint = json.loads((output / "v2_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "interrupted"
    assert "interrupted_at" in checkpoint


def test_v2_end_to_end_excludes_patch_context_items_from_detection(
    tmp_path: Path, monkeypatch
) -> None:
    detection_dir = tmp_path / "detection"
    detection_dir.mkdir()
    (detection_dir / "a.py").write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    (detection_dir / "b.py").write_text(
        "def divide2(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    manifest = {
        "evaluation_policy": {"patch_context_items": ["b"]},
        "items": [
            {"id": "a", "detection_file": "detection/a.py", "categories": ["division_by_zero"], "function": "divide"},
            {"id": "b", "detection_file": "detection/b.py", "categories": ["division_by_zero"], "function": "divide2"},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": [{"id": "a"}, {"id": "b"}]}), encoding="utf-8")

    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)

    def fake_pipeline(candidates, **kwargs):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr(main, "run_verify", fake_pipeline)

    args = main.build_parser().parse_args(
        [
            "--mode", "hybrid",
            "--input", str(detection_dir),
            "--ground-truth", str(ground_truth),
            "--output-dir", str(tmp_path / "out"),
        ]
    )

    assert main.mode_v2(args) == 0
    analyzed_files = {c.file for c in captured["candidates"]}
    assert analyzed_files == {str(detection_dir / "a.py")}


def test_summarize_v2_telemetry_reports_cache_hit_rate_per_stage():
    events = [
        {"stage": "detection", "status": "success", "duration_seconds": 1.0,
         "total_tokens": 100, "prompt_tokens": 80, "cached_tokens": 64},
        {"stage": "detection", "status": "success", "duration_seconds": 1.0,
         "total_tokens": 100, "prompt_tokens": 80, "cached_tokens": 0},
        {"stage": "synthesis", "status": "success", "duration_seconds": 1.0,
         "total_tokens": 100, "prompt_tokens": 80},  # e.g. codex backend: no cache field
    ]
    summary = main._summarize_v2_telemetry(events)
    assert summary["detection"]["calls_with_cache_data"] == 2
    assert summary["detection"]["cached_tokens"] == 64
    assert summary["detection"]["cache_hit_rate"] == 0.4
    assert summary["synthesis"]["calls_with_cache_data"] == 0
    assert summary["synthesis"]["cache_hit_rate"] is None


def test_summarize_detection_trace_keeps_failures_distinct():
    summary = main._summarize_detection_trace([
        {
            "function": "f",
            "located_candidates": 2,
            "classified_candidates": 1,
            "rejected_candidates": 1,
        },
        {
            "function": "g",
            "failure_stage": "classify",
            "error": "invalid JSON",
        },
    ])

    assert summary == {
        "units": 2,
        "located_candidates": 2,
        "classified_candidates": 1,
        "rejected_candidates": 1,
        "localization_failures": 0,
        "classification_failures": 1,
    }




def test_resume_retries_pipeline_errors_and_keeps_real_verdicts() -> None:
    checkpoint = {"verify_results": {"0": {"verdict": "CONFIRMED"}, "1": {"verdict": "PIPELINE_ERROR"},
                                     "2": {"verdict": "UNSUPPORTED"}}}

    assert sorted(main._resumable_results(checkpoint)) == [0, 2]


def test_detection_stage_stops_before_verification(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", lambda *a, **k: pytest.fail("verification must not run"))
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
                                           "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    report = json.loads((out / "v2_verify_report.json").read_text())
    assert report["coverage"] == {"status": "complete", "stage": "detection"}
    assert len(report["detection"]["candidates"]) == 1 and report["results"] == []


def test_detection_stage_skips_patch_context_items_like_end_to_end(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "det").mkdir()
    for name in ("kept", "patch_only"):
        (tmp_path / "det" / f"{name}.py").write_text("def divide(x: int, y: int) -> int:\n    return x // y\n")
    items = [{"id": name, "detection_file": f"det/{name}.py", "function": "divide", "categories": ["x"]}
             for name in ("kept", "patch_only")]
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"evaluation_policy": {"patch_context_items": ["patch_only"]}, "items": items}))
    (tmp_path / "ground_truths.json").write_text(json.dumps({"items": items}))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input",
                                           str(tmp_path / "det"), "--ground-truth",
                                           str(tmp_path / "ground_truths.json"), "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    files = json.loads((out / "v2_verify_report.json").read_text())["config"]["input_files"]
    assert [Path(f).name for f in files] == ["kept.py"]


def test_variants_enter_the_run_config(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    seen = {}
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: seen.update(kwargs) or _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--v2-variants", "A1,A2",
                                           "--input", str(source), "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    assert seen["v2_variants"] == ("A1", "A2")
    assert json.loads((out / "v2_verify_report.json").read_text())["config"]["v2_variants"] == ["A1", "A2"]
