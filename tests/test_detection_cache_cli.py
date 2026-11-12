import json
from pathlib import Path

import main
from research_pipeline.models import Finding


class _CountingAnalyzer:
    calls = 0

    def analyze(self, unit):
        type(self).calls += 1
        return [Finding(id="1", stage="llm_analysis", finding_type="suspected_bug", category="division_by_zero",
                        title="", explanation="", evidence=[], verifiable=True, confidence="high",
                        metadata={"expression": "x // y", "line": 2, "function": unit.qualname})]


def _run(tmp_path: Path, monkeypatch, out: str, cache: Path) -> dict:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _CountingAnalyzer())
    output = tmp_path / out
    argv = ["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source), "--output-dir", str(output),
            "--detection-cache", str(cache)]
    assert main.mode_v2(main.build_parser().parse_args(argv)) == 0
    return json.loads((output / "v2_verify_report.json").read_text())


def test_a_second_run_with_the_same_cache_makes_no_detection_calls(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    _CountingAnalyzer.calls = 0
    first = _run(tmp_path, monkeypatch, "out1", cache)
    assert _CountingAnalyzer.calls == 1
    second = _run(tmp_path, monkeypatch, "out2", cache)
    assert _CountingAnalyzer.calls == 1
    assert [c["expression"] for c in second["detection"]["candidates"]] == \
        [c["expression"] for c in first["detection"]["candidates"]]


def test_without_the_flag_nothing_is_cached(tmp_path, monkeypatch):
    _CountingAnalyzer.calls = 0
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _CountingAnalyzer())
    argv = ["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
            "--output-dir", str(tmp_path / "out")]
    assert main.mode_v2(main.build_parser().parse_args(argv)) == 0
    assert not (tmp_path / "cache").exists()
