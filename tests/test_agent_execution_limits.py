from types import SimpleNamespace

from research_pipeline.verify import agent_arm


def _case(tmp_path):
    (tmp_path / "original.py").write_text("def f(x):\n    return 1 // x\n")
    return tmp_path


def test_api_agent_never_accepts_a_verdict_after_its_deadline(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(agent_arm.time, "monotonic", lambda: clock[0])
    seen = []

    class LLM:
        def complete(self, system, user, *, timeout_seconds=None):
            seen.append(timeout_seconds)
            clock[0] += 0.4
            return SimpleNamespace(harness="pass", model="fake", telemetry={})

    def run(command, **kwargs):
        seen.append(kwargs["timeout"])
        clock[0] += 0.7
        return SimpleNamespace(stdout="VERIFICATION SUCCESSFUL", stderr="", returncode=0)

    monkeypatch.setattr(agent_arm.subprocess, "run", run)
    result = agent_arm.api_agent(LLM(), esbmc_timeout=5)("f", _case(tmp_path), 1)
    assert result == "out of time"
    assert seen == [1.0, 0.6]


def test_api_agent_preserves_command_flags_and_operation_limits(tmp_path, monkeypatch):
    seen = {}

    class LLM:
        def complete(self, system, user, *, timeout_seconds=None):
            seen["llm_timeout"] = timeout_seconds
            return SimpleNamespace(harness="pass", model="fake", telemetry={})

    def run(command, **kwargs):
        seen["command"] = command
        seen["esbmc_timeout"] = kwargs["timeout"]
        return SimpleNamespace(stdout="VERIFICATION SUCCESSFUL", stderr="", returncode=0)

    monkeypatch.setattr(agent_arm.subprocess, "run", run)
    agent = agent_arm.api_agent(LLM(), esbmc=["/fake/esbmc", "--z3"], esbmc_timeout=7, llm_timeout=3)
    assert agent("f", _case(tmp_path), 20) == "DONE"
    assert seen["command"][:2] == ["/fake/esbmc", "--z3"]
    assert seen["llm_timeout"] == 3
    assert 0 < seen["esbmc_timeout"] <= 7


def test_llm_retries_share_the_per_call_deadline(monkeypatch):
    from urllib.error import URLError
    import pytest
    from research_pipeline.verify import llm_client

    clock, requests = [0.0], []
    monkeypatch.setattr(llm_client.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(llm_client.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    def offline(request, *, timeout):
        requests.append(timeout)
        raise URLError("offline")

    monkeypatch.setattr(llm_client.request, "urlopen", offline)
    client = llm_client.LLMClient(backend="ollama", timeout_seconds=99)
    with pytest.raises(TimeoutError):
        client.complete("system", "user", timeout_seconds=1)
    assert requests == [1.0]
    assert clock[0] == 1.0


def test_call_deadline_interrupts_slow_response_reads(monkeypatch):
    import time
    import pytest
    from research_pipeline.verify import llm_client

    class SlowResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            # Model a transfer that remains active but exceeds the total budget.
            time.sleep(2)
            return b'{"output_text":"{}"}'

    monkeypatch.setattr(llm_client.request, "urlopen", lambda *a, **k: SlowResponse())
    client = llm_client.LLMClient(backend="ollama")
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        client.complete("system", "user", timeout_seconds=0.1)
    assert time.monotonic() - started < 1
