"""A plan or quota limit stops the run with the checkpoint saved, instead of turning every remaining case into
PIPELINE_ERROR (item 23, run of 03/11: 103 PIPELINE_ERROR after the Claude 5-hour limit)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib import error

import pytest

import main
from research_pipeline.llm.rate_limit import USAGE_LIMIT_EXIT, UsageLimitReached, exit_on_usage_limit, is_usage_limit
from research_pipeline.models import Finding
from research_pipeline.scan.pipeline import execute_scan, plan_scan
from research_pipeline.smells.filter import SmellCandidate, filter_candidates
from research_pipeline.verify import agent_arm, loop
from research_pipeline.verify.agent_scan import agent_verifier
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.llm_client import LLMClient
from research_pipeline.verify.orchestrator import orchestrate


@pytest.mark.parametrize("text", [
    "You've hit your 5-hour limit · resets 1:30am (America/Manaus)",
    "You’ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro)",
    "You've hit your monthly spend limit · raise it",
    "[429] Claude usage limit reached.",
    "Claude AI usage limit reached|1730000000",
    '400 {"error": {"message": "Your credit balance is too low to access the Anthropic API."}}',
    '429 {"error": {"code": "insufficient_quota"}}',
])
def test_limit_messages_seen_in_runs_are_recognized(text):
    assert is_usage_limit(text)


@pytest.mark.parametrize("text", [
    "API Error: Can't reach the API server (EAI_AGAIN)",
    "claude -p saiu com código 1: ",
    "Timeout ao chamar claude -p.",
    "",
])
def test_other_failures_are_not_a_limit(text):
    assert not is_usage_limit(text)


class _Completed:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


_LIMIT = json.dumps({"type": "result", "is_error": True, "api_error_status": 429,
                     "result": "You've hit your 5-hour limit · resets 1:30am (America/Manaus)"})


def test_claude_cli_synthesis_raises_the_limit(monkeypatch):
    monkeypatch.setattr("research_pipeline.verify.llm_client.subprocess.run",
                        lambda command, **kwargs: _Completed(_LIMIT, returncode=1))
    with pytest.raises(UsageLimitReached, match="5-hour limit"):
        LLMClient(backend="claude_cli").complete("system", "user")


def test_claude_cli_detection_raises_the_limit(monkeypatch):
    from research_pipeline.llm.backends.claude_cli import ClaudeCliAnalyzer
    from research_pipeline.models import CodeUnit
    monkeypatch.setattr("research_pipeline.llm.backends.claude_cli.subprocess.run",
                        lambda command, **kwargs: _Completed(_LIMIT, returncode=1))
    unit = CodeUnit(path=Path("m.py"), name="f", qualname="f", source="def f(x):\n    return 1 // x\n",
                    start_line=1, end_line=2, parameters=["x"], type_hints={}, operations=[], loops=[],
                    conditionals=[], guards=[], metrics={})
    with pytest.raises(UsageLimitReached):
        ClaudeCliAnalyzer().analyze(unit)


def test_a_claude_cli_failure_without_the_limit_stays_a_plain_error(monkeypatch):
    envelope = json.dumps({"is_error": True, "result": "model not found"})
    monkeypatch.setattr("research_pipeline.verify.llm_client.subprocess.run",
                        lambda command, **kwargs: _Completed(envelope, returncode=1))
    with pytest.raises(RuntimeError, match="model not found") as caught:
        LLMClient(backend="claude_cli").complete("system", "user")
    assert not isinstance(caught.value, UsageLimitReached)


def test_codex_usage_limit_raises_the_limit(monkeypatch):
    failed = json.dumps({"type": "turn.failed", "error": {"message": "You’ve hit your usage limit."}})
    monkeypatch.setattr("research_pipeline.verify.llm_client.subprocess.run",
                        lambda command, **kwargs: _Completed(failed + "\n"))
    with pytest.raises(UsageLimitReached):
        LLMClient(backend="codex").complete("system", "user")


def _http_error(code: int, body: str):
    def urlopen(*_args, **_kwargs):
        raise error.HTTPError("https://api.anthropic.com/v1/messages", code, "x", {}, io.BytesIO(body.encode()))
    return urlopen


@pytest.mark.parametrize("code", [429, 529])
def test_anthropic_still_limited_after_the_retries_raises_the_limit(monkeypatch, code):
    monkeypatch.setattr("research_pipeline.verify.llm_client.request.urlopen", _http_error(code, '{"error": {}}'))
    monkeypatch.setattr("research_pipeline.verify.llm_client.time.sleep", lambda seconds: None)
    with pytest.raises(UsageLimitReached, match=str(code)):
        LLMClient(backend="anthropic", model="claude-sonnet-5-5", api_key="k").complete("system", "user")


def test_anthropic_bad_request_stays_a_plain_error(monkeypatch):
    monkeypatch.setattr("research_pipeline.verify.llm_client.request.urlopen",
                        _http_error(400, '{"error": {"message": "max_tokens too large"}}'))
    with pytest.raises(RuntimeError) as caught:
        LLMClient(backend="anthropic", model="claude-sonnet-5-5", api_key="k").complete("system", "user")
    assert not isinstance(caught.value, UsageLimitReached)


def _hypotheses(tmp_path: Path, count: int) -> list[BugHypothesis]:
    source = tmp_path / "m.py"
    source.write_text("def f(a: int, b: int) -> int:\n    return a // b\n", encoding="utf-8")
    return [BugHypothesis(file=str(source), function="f", suspect_expression=f"a // b  # {i}") for i in range(count)]


def test_run_verify_stops_at_the_limit_and_keeps_what_finished(tmp_path, monkeypatch):
    calls = []

    def verify_hypothesis(h, **_kwargs):
        calls.append(h)
        if len(calls) == 1:
            raise ValueError("broken case")
        raise UsageLimitReached("You've hit your 5-hour limit")

    monkeypatch.setattr(loop, "verify_hypothesis", verify_hypothesis)
    saved = {}
    with pytest.raises(UsageLimitReached):
        loop.run_verify(_hypotheses(tmp_path, 3), llm=None, output_dir=tmp_path, on_result=saved.__setitem__)
    assert len(calls) == 2
    assert [d["verdict"] for d in saved.values()] == ["PIPELINE_ERROR"]


def _hypothesis_dict(h: BugHypothesis) -> dict:
    return {"hypothesis": h.to_dict(), "verdict": "UNSUPPORTED", "reason": ""}


def test_agent_verifier_stops_at_the_limit(tmp_path, monkeypatch):
    def run_agent_arm(*_args, **_kwargs):
        raise UsageLimitReached("limit")

    monkeypatch.setattr("research_pipeline.verify.agent_scan.run_agent_arm", run_agent_arm)
    verify = agent_verifier(lambda *a: "DONE", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                            agent_timeout=1)
    saved = {}
    with pytest.raises(UsageLimitReached):
        verify(_hypotheses(tmp_path, 2), llm=None, output_dir=tmp_path, completed={}, on_result=saved.__setitem__)
    assert not saved


def test_agent_session_stopped_by_the_limit_ends_the_run(tmp_path):
    h = _hypotheses(tmp_path, 1)[0]
    with pytest.raises(UsageLimitReached, match="5-hour limit"):
        agent_arm.run_agent_arm(h, work_dir=tmp_path / "work", esbmc_command=["esbmc"], bound=5, timeout_seconds=30,
                                run_agent=lambda prompt, cwd, timeout: "You've hit your 5-hour limit · resets 1am")


def test_api_agent_lets_the_limit_through(tmp_path):
    class Limited:
        def complete(self, *_args, **_kwargs):
            raise UsageLimitReached("limit")

    (tmp_path / "original.py").write_text("def f():\n    pass\n", encoding="utf-8")
    run = agent_arm.api_agent(Limited())
    with pytest.raises(UsageLimitReached):
        run("run the function `f`", tmp_path, 60)


def test_agent_fallback_stops_at_the_limit(tmp_path, monkeypatch):
    def run_agent_arm(*_args, **_kwargs):
        raise UsageLimitReached("limit")

    monkeypatch.setattr(agent_arm, "run_agent_arm", run_agent_arm)
    state = {}
    with pytest.raises(UsageLimitReached):
        agent_arm.run_agent_fallback([_hypothesis_dict(h) for h in _hypotheses(tmp_path, 2)],
                                     run_agent=lambda *a: "", work_dir=tmp_path, esbmc_command=["esbmc"], bound=5,
                                     timeout_seconds=1, agent_timeout=1, sources=None, state=state,
                                     save=lambda: None, config={})
    assert state["agent_results"] == {}


def test_orchestrate_stops_at_the_limit():
    def arm(_result):
        raise UsageLimitReached("limit")

    result = {"hypothesis": {"hypothesis_id": "h1"}, "verdict": "UNSUPPORTED"}
    with pytest.raises(UsageLimitReached):
        orchestrate([result], arms={"agent": arm}, state={}, save=lambda: None, route=lambda r: ["agent"])


def test_smell_filter_stops_at_the_limit():
    class Limited:
        def complete(self, *_args, **_kwargs):
            raise UsageLimitReached("limit")

    candidate = SmellCandidate("c1", "long_method", "m.py", 1, "ruff:PLR0915", {}, "def f():\n    pass\n")
    with pytest.raises(UsageLimitReached):
        filter_candidates([candidate], Limited())


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "m.py").write_text("def a(x: int) -> int:\n    return 1 // x\n\n\ndef b(x: int) -> int:\n"
                               "    return 2 // x\n\n\ndef c(x: int) -> int:\n    return 3 // x\n", encoding="utf-8")
    return repo


class _LimitedAnalyzer:
    """Answers the first call, then hits the limit."""
    model = "fake"

    def __init__(self):
        self.calls = 0
        self.telemetry_events = []

    def analyze(self, _unit):
        self.calls += 1
        if self.calls > 1:
            raise UsageLimitReached("You've hit your 5-hour limit")
        return [Finding(id="f", stage="llm_analysis", finding_type="suspected_bug", category="", title="",
                        explanation="", evidence=[], verifiable=True, confidence="high",
                        metadata={"expression": "1 // x"})]


def test_scan_detection_stops_at_the_limit_with_the_checkpoint_saved(tmp_path):
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    analyzer = _LimitedAnalyzer()
    with pytest.raises(UsageLimitReached):
        execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=lambda *a, **k: [])
    assert analyzer.calls == 2
    checkpoint = json.loads((tmp_path / "out" / "scan_checkpoint.json").read_text(encoding="utf-8"))
    assert [entry["error"] for entry in checkpoint["detection"].values()] == [""]


def _v2_args(tmp_path: Path) -> list[str]:
    source = tmp_path / "sample.py"
    source.write_text("def a(x: int) -> int:\n    return 1 // x\n\n\ndef b(x: int) -> int:\n    return 2 // x\n\n\n"
                      "def c(x: int) -> int:\n    return 3 // x\n", encoding="utf-8")
    return ["--mode", "hybrid", "--input", str(source), "--output-dir", str(tmp_path / "out")]


class _Synthesizer:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]


def test_v2_detection_stops_at_the_limit_and_exits_apart(tmp_path, monkeypatch, capsys):
    analyzer = _LimitedAnalyzer()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: analyzer)
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    assert main.mode_v2(main.build_parser().parse_args(_v2_args(tmp_path))) == USAGE_LIMIT_EXIT
    assert analyzer.calls == 2
    checkpoint = json.loads((tmp_path / "out" / "v2_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["interruption_reason"] == "usage_limit"
    assert len(checkpoint["detection_units"]) == 1
    assert "--resume" in capsys.readouterr().err


def test_v2_verify_stops_at_the_limit_with_the_checkpoint_saved(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _LimitedAnalyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "resolve_rules", lambda *a, **k: {"disabled_rules": []})

    def limited(hypotheses, *, on_result, **_kwargs):
        on_result(0, {"hypothesis": hypotheses[0].to_dict(), "verdict": "CONFIRMED", "reason": ""})
        raise UsageLimitReached("You've hit your 5-hour limit")

    monkeypatch.setattr(main, "run_verify", limited)
    source = tmp_path / "one.py"
    source.write_text("def a(x: int) -> int:\n    return 1 // x\n", encoding="utf-8")
    args = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(tmp_path / "out")]
    assert main.mode_v2(main.build_parser().parse_args(args)) == USAGE_LIMIT_EXIT
    checkpoint = json.loads((tmp_path / "out" / "v2_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "interrupted"
    assert checkpoint["interruption_reason"] == "usage_limit"
    assert checkpoint["verify_results"]["0"]["verdict"] == "CONFIRMED"
    assert "5-hour limit" in capsys.readouterr().err


def test_scripts_exit_apart_on_the_limit(capsys):
    def script():
        raise UsageLimitReached("limit")

    assert exit_on_usage_limit(script) == USAGE_LIMIT_EXIT
    assert "Limite de uso" in capsys.readouterr().err


def test_judge_smells_stops_at_the_limit(tmp_path):
    from research_pipeline.scan.pipeline import judge_smells
    root = tmp_path / "repo"
    root.mkdir()
    (root / "loja.py").write_text("class P:\n    def a(self, c):\n        return c.x + c.y\n", encoding="utf-8")
    plan = plan_scan(root, tmp_path / "out", smells=True)

    class Limited:
        def complete(self, *_args, **_kwargs):
            raise UsageLimitReached("limit")

    with pytest.raises(UsageLimitReached):
        judge_smells(plan, Limited())


def test_cli_scan_exits_apart_on_the_limit(tmp_path, monkeypatch, capsys):
    def limited(_plan, **_kwargs):
        raise UsageLimitReached("You've hit your 5-hour limit")

    monkeypatch.setattr(main, "build_analyzer", lambda **kw: _LimitedAnalyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "execute_scan", limited)
    monkeypatch.setattr("sys.argv", ["main.py", "--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir",
                                     str(tmp_path / "out"), "--backend", "openai", "--model", "gpt-5.5", "--yes",
                                     "--esbmc-command", "esbmc"])
    assert main.main() == USAGE_LIMIT_EXIT
    assert "scan_checkpoint.json" in capsys.readouterr().err
