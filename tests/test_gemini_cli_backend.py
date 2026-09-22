"""Contract tests for the local Gemini CLI backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_pipeline.llm.backends.factory import build_analyzer
from research_pipeline.llm.backends.gemini_cli import GeminiCliAnalyzer
from research_pipeline.models import CodeUnit
from research_pipeline.scan.synth import HarnessSynthesizer
from main import _infer_backend


def _unit() -> CodeUnit:
    return CodeUnit(
        path=Path("m.py"), name="f", qualname="f",
        source="def f(x: int) -> int:\n    return 10 // x\n",
        start_line=1, end_line=2, parameters=["x"], type_hints={"x": "int"},
        operations=[], loops=[], conditionals=[], guards=[], metrics={},
    )


class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def test_factory_wires_gemini_cli_backend():
    analyzer = build_analyzer(backend="gemini_cli")
    assert isinstance(analyzer, GeminiCliAnalyzer)
    assert analyzer.model == ""


def test_model_alias_gemini_cli_infers_cli_backend():
    assert _infer_backend("gemini_cli") == "gemini_cli"


def test_gemini_cli_analyzer_parses_json_response_and_uses_plan_mode(monkeypatch):
    payload = {"findings": []}
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return _FakeCompleted(json.dumps({"response": json.dumps(payload)}))

    monkeypatch.setattr(
        "research_pipeline.llm.backends.gemini_cli.subprocess.run", fake_run,
    )
    assert GeminiCliAnalyzer().analyze(_unit()) == []
    command = captured["command"]
    assert command[0] == "gemini"
    assert "--prompt" in command
    assert "--output-format" in command
    assert "json" in command
    assert "--approval-mode" in command
    assert "plan" in command


def test_gemini_cli_analyzer_passes_model_when_configured(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return _FakeCompleted(json.dumps({"response": '{"findings": []}'}))

    monkeypatch.setattr(
        "research_pipeline.llm.backends.gemini_cli.subprocess.run", fake_run,
    )
    GeminiCliAnalyzer(model="gemini-2.5-flash-lite").analyze(_unit())
    assert captured["command"][captured["command"].index("--model") + 1] == "gemini-2.5-flash-lite"


def test_gemini_cli_synthesizer_extracts_response_text(monkeypatch):
    from research_pipeline.models import Finding

    finding = Finding(
        id="f1", stage="scan_candidate", finding_type="suspected_bug",
        category="division_by_zero", title="", explanation="",
        evidence=[], verifiable=True, confidence="medium",
        metadata={"expression": "10 // x"},
    )

    def fake_run(command, **kwargs):
        return _FakeCompleted(json.dumps({"response": "```python\ndef main():\n    pass\n```"}))

    monkeypatch.setattr(
        "research_pipeline.scan.synth.subprocess.run", fake_run,
    )
    result = HarnessSynthesizer(backend="gemini_cli").synthesize(_unit(), finding)
    assert "def main():" in result.harness
    assert "```" not in result.harness


def test_gemini_cli_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        "research_pipeline.llm.backends.gemini_cli.subprocess.run",
        lambda command, **kwargs: _FakeCompleted("", returncode=1, stderr="boom"),
    )
    with pytest.raises(RuntimeError, match="código 1"):
        GeminiCliAnalyzer().analyze(_unit())
