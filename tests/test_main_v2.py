from __future__ import annotations

from pathlib import Path

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


def test_print_cache_summary_shows_rate_and_missing_data(capsys):
    main._print_cache_summary({
        "detection": {"cache_hit_rate": 0.4, "cached_tokens": 64, "prompt_tokens": 160},
        "synthesis": {"cache_hit_rate": None, "cached_tokens": 0, "prompt_tokens": 0},
    })
    out = capsys.readouterr().out
    assert "detection: 40%" in out
    assert "64/160 tokens" in out
    assert "synthesis: sem dado de cache" in out
