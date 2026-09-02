from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import main  # noqa: E402
from research_pipeline.models import Finding  # noqa: E402


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
            "--mode", "v2", "--input", str(source),
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
    base = ["--mode", "v2", "--input", str(source), "--output-dir", str(output)]

    assert main.mode_v2(parser.parse_args(base)) == 0
    assert _Analyzer.calls == 1
    assert main.mode_v2(parser.parse_args([*base, "--resume"])) == 0
    assert _Analyzer.calls == 1
