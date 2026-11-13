from __future__ import annotations

import json
import subprocess

from research_pipeline.llm.backends import claude_cli
from research_pipeline.llm.backends.claude_cli import ClaudeCliAnalyzer
from research_pipeline.verify import llm_client
from research_pipeline.verify.llm_client import LLMClient

DENIED = "Read Write Edit Bash Glob Grep WebFetch WebSearch Task"


class _Recorder:
    def __init__(self, envelope: dict) -> None:
        self.envelope, self.calls = envelope, []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(self.envelope), "")


def test_detection_command_without_isolation_is_the_historical_one(monkeypatch) -> None:
    recorder = _Recorder({"structured_output": [], "usage": {}})
    monkeypatch.setattr(claude_cli.subprocess, "run", recorder)
    ClaudeCliAnalyzer(model="m")._run_cli("SYS", "USER", schema={"type": "array"})
    command, kwargs = recorder.calls[0]
    assert command == ["claude", "--print", "--output-format", "json", "--json-schema", '{"type": "array"}',
                       "--disallowed-tools", DENIED, "--permission-prompts", "none", "--no-session-persistence",
                       "--model", "m", "SYS\n\nUSER"]
    assert "cwd" not in kwargs


def test_synthesis_command_without_isolation_is_the_historical_one(monkeypatch) -> None:
    recorder = _Recorder({"result": "ok", "usage": {}})
    monkeypatch.setattr(llm_client.subprocess, "run", recorder)
    LLMClient(backend="claude_cli", model="m")._run_claude_cli("SYS", "USER")
    command, kwargs = recorder.calls[0]
    assert command == ["claude", "--print", "--output-format", "json", "--disallowed-tools", DENIED,
                       "--permission-prompts", "none", "--no-session-persistence", "--model", "m", "SYS\n\nUSER"]
    assert "cwd" not in kwargs


def _isolated_flags(command: list[str]) -> None:
    assert command[command.index("--system-prompt") + 1] == "SYS"
    assert command[command.index("--tools") + 1] == ""
    assert "--disable-slash-commands" in command and "--strict-mcp-config" in command
    assert command[-1] == "USER"


def test_isolated_detection_sends_the_system_prompt_apart_and_runs_in_an_empty_directory(monkeypatch) -> None:
    recorder = _Recorder({"structured_output": [], "usage": {}})
    monkeypatch.setattr(claude_cli.subprocess, "run", recorder)
    ClaudeCliAnalyzer(model="m", isolated=True)._run_cli("SYS", "USER", schema={"type": "array"})
    command, kwargs = recorder.calls[0]
    _isolated_flags(command)
    assert kwargs["cwd"]


def test_isolated_synthesis_uses_the_same_flags(monkeypatch) -> None:
    recorder = _Recorder({"result": "ok", "usage": {}})
    monkeypatch.setattr(llm_client.subprocess, "run", recorder)
    LLMClient(backend="claude_cli", model="m", isolated=True)._run_claude_cli("SYS", "USER")
    _isolated_flags(recorder.calls[0][0])
    assert recorder.calls[0][1]["cwd"]
