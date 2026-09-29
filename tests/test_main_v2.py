from __future__ import annotations

import json
from pathlib import Path

import main
from research_pipeline.models import Finding
from research_pipeline.scan.pipeline import ScanCandidate, ScanCaseResult


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


def test_parser_accepts_pytest_counterexample_options() -> None:
    args = main.build_parser().parse_args([
        "--mode", "hybrid", "--input", "sample.py",
        "--generate-pytest-testcase", "--pytest-output-dir", "artifacts/pytest",
    ])
    assert args.generate_pytest_testcase is True
    assert args.pytest_output_dir == "artifacts/pytest"


def test_parser_accepts_two_stage_detection_strategy() -> None:
    parser = main.build_parser()
    assert parser.parse_args(["--mode", "hybrid", "--input", "sample.py"]).detection_strategy == "single"
    assert parser.parse_args([
        "--mode", "hybrid", "--input", "sample.py",
        "--detection-strategy", "two_stage",
    ]).detection_strategy == "two_stage"


def test_v2_telemetry_separates_two_stage_detection_calls() -> None:
    summary = main._summarize_v2_telemetry([
        {"stage": "detection", "analysis_stage": "localize", "status": "success"},
        {"stage": "detection", "analysis_stage": "classify", "status": "success"},
        {"stage": "detection", "analysis_stage": "classify", "status": "error"},
    ])

    assert summary["detection"]["localization_calls"] == 1
    assert summary["detection"]["classification_calls"] == 2


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
                id="fake-smell-bug",
                stage="llm_analysis",
                finding_type="suspected_bug",
                category="many_parameters",
                title="",
                explanation="not a formal bug",
                evidence=[],
                verifiable=True,
                confidence="high",
                metadata={"expression": "f(...)"},
            ),
        ]


def test_v2_does_not_forward_smells_to_synthesis(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(value: int) -> int:\n    return value\n", encoding="utf-8")
    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _AnalyzerWithSmell())
    monkeypatch.setattr(main, "HarnessSynthesizer", _Synthesizer)
    monkeypatch.setattr(main, "run_pipeline_scan", lambda candidates, **kwargs: captured.setdefault("candidates", candidates) or [])

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
    monkeypatch.setattr(main, "HarnessSynthesizer", _Synthesizer)

    def fake_pipeline(candidates, **kwargs):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr(main, "run_pipeline_scan", fake_pipeline)
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
    assert candidate.category == "division_by_zero"
    assert candidate.expression == "x // y"


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
    monkeypatch.setattr(main, "HarnessSynthesizer", _Synthesizer)
    monkeypatch.setattr(main, "run_pipeline_scan", lambda candidates, **kwargs: [])
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
    monkeypatch.setattr(main, "HarnessSynthesizer", _Synthesizer)

    def interrupted_pipeline(candidates, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "run_pipeline_scan", interrupted_pipeline)
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
    monkeypatch.setattr(main, "HarnessSynthesizer", _Synthesizer)

    def fake_pipeline(candidates, **kwargs):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr(main, "run_pipeline_scan", fake_pipeline)

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


def test_print_cache_summary_shows_rate_and_missing_data(capsys):
    main._print_cache_summary({
        "detection": {"cache_hit_rate": 0.4, "cached_tokens": 64, "prompt_tokens": 160},
        "synthesis": {"cache_hit_rate": None, "cached_tokens": 0, "prompt_tokens": 0},
    })
    out = capsys.readouterr().out
    assert "detection: 40%" in out
    assert "64/160 tokens" in out
    assert "synthesis: sem dado de cache" in out


def test_scan_summary_counts_harness_tiers(tmp_path: Path) -> None:
    candidate = ScanCandidate(file=str(tmp_path / "x.py"), function="f", category="division_by_zero")
    results = [
        ScanCaseResult(candidate, "confirmed_native", harness_tier="native"),
        ScanCaseResult(candidate, "confirmed_on_abstraction", harness_tier="scalar"),
        ScanCaseResult(candidate, "invalid_harness", harness_tier="scalar"),
    ]

    summary = main._scan_summary(results)

    assert summary["harness_tiers"] == {
        "native": 1,
        "scalar": 2,
    }
    assert summary["by_category"]["division_by_zero"]["confirmed"] == 1
    assert summary["by_category"]["division_by_zero"]["abstraction_only"] == 1


def test_rewrite_mode_defaults_off_and_is_forwarded(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "HarnessSynthesizer", _Synthesizer)
    monkeypatch.setattr(main, "run_pipeline_scan", lambda candidates, **kwargs: captured.update(kwargs) or [])
    parser = main.build_parser()
    base = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(tmp_path / "out")]

    assert parser.parse_args(base).rewrite_mode == "off"
    assert main.mode_v2(parser.parse_args([*base, "--rewrite-mode", "validated"])) == 0
    assert captured["rewrite_mode"] == "validated"
    assert type(captured["replay_executor"]).__name__ == "LocalReplayExecutor"
    config = json.loads((tmp_path / "out" / "v2_report.json").read_text(encoding="utf-8"))["config"]
    assert config["rewrite_mode"] == "validated"
    assert config["replay_image"] == ""
