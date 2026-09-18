"""Tests for the `claude_cli` backend (detection + harness synthesis).

Mirrors CodexAnalyzer's "no metered API key" niche using `claude -p` instead
of `codex exec` -- billed against a Claude subscription/API access already on
the account, not a separate OPENAI_API_KEY/GEMINI_API_KEY. `subprocess.run`
is monkeypatched throughout; no real `claude` invocation is made (that was
verified once by hand, matching the pattern the module's own docstring/tests
for CodexAnalyzer already follow, and is out of scope for the default suite
per --repeat/live_llm cost discipline elsewhere in this repo).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_pipeline.llm.backends.claude_cli import ClaudeCliAnalyzer
from research_pipeline.llm.backends.factory import build_analyzer
from research_pipeline.models import CodeUnit
from research_pipeline.scan.synth import HarnessSynthesizer


def _unit() -> CodeUnit:
    return CodeUnit(
        path=Path("m.py"), name="f", qualname="f",
        source="def f(x: int) -> int:\n    return 10 // x\n",
        start_line=1, end_line=2, parameters=["x"], type_hints={"x": "int"},
        operations=[], loops=[], conditionals=[], guards=[], metrics={},
    )


def _envelope(**overrides) -> str:
    base = {
        "is_error": False,
        "result": "",
        "structured_output": {"findings": []},
        "usage": {"input_tokens": 100, "output_tokens": 20},
        "total_cost_usd": 0.01,
    }
    base.update(overrides)
    return json.dumps(base)


class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


# --- factory wiring ----------------------------------------------------------


def test_build_analyzer_claude_cli_returns_claude_cli_analyzer():
    analyzer = build_analyzer(backend="claude_cli")
    assert isinstance(analyzer, ClaudeCliAnalyzer)
    assert analyzer.model == ""


def test_build_analyzer_claude_cli_model_override():
    analyzer = build_analyzer(backend="claude_cli", llm_model="opus")
    assert analyzer.model == "opus"


# --- ClaudeCliAnalyzer.analyze -----------------------------------------------


def test_analyze_happy_path_uses_structured_output_directly(monkeypatch):
    findings_payload = {"findings": [{
        "finding_type": "suspected_bug", "category": "division_by_zero",
        "verifiable": True, "explanation": "x may be 0",
        "metadata": {"expression": "10 // x", "line": 2, "operands": ["x"],
                     "guard_evidence": "none", "missing_guard": "x != 0", "context_needed": []},
    }]}
    captured_command = {}

    def fake_run(command, **kwargs):
        captured_command["command"] = command
        return _FakeCompleted(_envelope(structured_output=findings_payload))

    monkeypatch.setattr("research_pipeline.llm.backends.claude_cli.subprocess.run", fake_run)
    analyzer = ClaudeCliAnalyzer()
    findings = analyzer.analyze(_unit())

    assert len(findings) == 1
    assert findings[0].category == "division_by_zero"
    command = captured_command["command"]
    assert "--json-schema" in command
    assert "--disallowed-tools" in command
    assert "--permission-prompts" in command
    assert "none" in command
    assert "--no-session-persistence" in command
    assert len(analyzer.telemetry_events) == 1


def test_analyze_passes_model_flag_when_set(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return _FakeCompleted(_envelope())

    monkeypatch.setattr("research_pipeline.llm.backends.claude_cli.subprocess.run", fake_run)
    ClaudeCliAnalyzer(model="opus").analyze(_unit())
    assert "--model" in captured["command"]
    assert "opus" in captured["command"]


def test_analyze_omits_model_flag_when_unset(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return _FakeCompleted(_envelope())

    monkeypatch.setattr("research_pipeline.llm.backends.claude_cli.subprocess.run", fake_run)
    ClaudeCliAnalyzer().analyze(_unit())
    assert "--model" not in captured["command"]


def test_analyze_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        "research_pipeline.llm.backends.claude_cli.subprocess.run",
        lambda command, **kwargs: _FakeCompleted("", returncode=1, stderr="boom"),
    )
    with pytest.raises(RuntimeError, match="código 1"):
        ClaudeCliAnalyzer().analyze(_unit())


def test_analyze_raises_on_is_error_true(monkeypatch):
    monkeypatch.setattr(
        "research_pipeline.llm.backends.claude_cli.subprocess.run",
        lambda command, **kwargs: _FakeCompleted(_envelope(is_error=True, result="refused")),
    )
    with pytest.raises(RuntimeError, match="turno falhou"):
        ClaudeCliAnalyzer().analyze(_unit())


def test_analyze_raises_when_structured_output_missing(monkeypatch):
    # Simulates an older `claude` binary without --json-schema support.
    envelope = json.loads(_envelope())
    del envelope["structured_output"]
    monkeypatch.setattr(
        "research_pipeline.llm.backends.claude_cli.subprocess.run",
        lambda command, **kwargs: _FakeCompleted(json.dumps(envelope)),
    )
    with pytest.raises(RuntimeError, match="structured_output"):
        ClaudeCliAnalyzer().analyze(_unit())


def test_analyze_raises_on_command_not_found(monkeypatch):
    def fake_run(command, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("research_pipeline.llm.backends.claude_cli.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="não encontrado no PATH"):
        ClaudeCliAnalyzer().analyze(_unit())


def test_analyze_raises_on_timeout(monkeypatch):
    import subprocess as subprocess_module

    def fake_run(command, **kwargs):
        raise subprocess_module.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr("research_pipeline.llm.backends.claude_cli.subprocess.run", fake_run)
    with pytest.raises(TimeoutError):
        ClaudeCliAnalyzer(timeout_seconds=1).analyze(_unit())


# --- HarnessSynthesizer (synth stage) -----------------------------------------


def test_harness_synthesizer_accepts_claude_cli_backend():
    synth = HarnessSynthesizer(backend="claude_cli")
    assert synth.backend == "claude_cli"


def test_synth_via_claude_cli_extracts_python_fence(monkeypatch):
    harness_code = "```python\ndef main():\n    pass\n```"

    def fake_run(command, **kwargs):
        return _FakeCompleted(_envelope(result=harness_code))

    monkeypatch.setattr("research_pipeline.scan.synth.subprocess.run", fake_run)
    synth = HarnessSynthesizer(backend="claude_cli")
    candidate_finding = _finding_for_synth()
    result = synth.synthesize(_unit(), candidate_finding)
    assert "def main():" in result.harness
    assert "```" not in result.harness


def test_synth_via_claude_cli_raises_on_is_error(monkeypatch):
    monkeypatch.setattr(
        "research_pipeline.scan.synth.subprocess.run",
        lambda command, **kwargs: _FakeCompleted(_envelope(is_error=True, result="refused")),
    )
    synth = HarnessSynthesizer(backend="claude_cli")
    with pytest.raises(RuntimeError, match="turno falhou"):
        synth.synthesize(_unit(), _finding_for_synth())


def _finding_for_synth():
    from research_pipeline.models import Finding
    return Finding(
        id="f1", stage="scan_candidate", finding_type="suspected_bug",
        category="division_by_zero", title="", explanation="",
        evidence=[], verifiable=True, confidence="medium",
        metadata={"expression": "10 // x"},
    )
