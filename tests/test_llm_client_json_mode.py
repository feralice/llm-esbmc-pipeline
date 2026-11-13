from __future__ import annotations

import pytest

from research_pipeline.verify.llm_client import LLMClient


def _payload(backend: str, json_mode: bool) -> dict:
    client = LLMClient(backend=backend, model="m", api_key="k", base_url="http://x/v1")
    seen = {}
    client._post_json = lambda payload: seen.update(payload) or {"choices": [{"message": {"content": "{}"}}]}
    client.complete("SYS", "USER", json_mode=json_mode)
    return seen


@pytest.mark.parametrize("backend", ["ollama", "google"])
def test_chat_completions_backends_get_the_json_response_format(backend: str) -> None:
    assert _payload(backend, True)["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("backend", ["ollama", "google"])
def test_no_response_format_without_json_mode(backend: str) -> None:
    assert "response_format" not in _payload(backend, False)


def _client(policy=None) -> LLMClient:
    client = LLMClient(backend="ollama", model="m", api_key="k", base_url="http://x/v1", policy=policy)
    return client


def test_client_without_policy_returns_an_empty_answer_as_before() -> None:
    client = _client()
    client._post_json = lambda payload: {"choices": [{"message": {"content": ""}}]}
    with pytest.raises(RuntimeError):
        client.complete("S", "U")


def test_client_retries_empty_and_timeout_and_records_it(monkeypatch) -> None:
    from research_pipeline.llm.failure_policy import FailurePolicy

    monkeypatch.setattr("research_pipeline.llm.failure_policy.time.sleep", lambda s: None)
    client = _client(FailurePolicy(retries=2))
    answers = [TimeoutError("t"), {"choices": [{"message": {"content": ""}}]},
               {"choices": [{"message": {"content": "{}"}}]}]

    def post(payload):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    client._post_json = post
    result = client.complete("S", "U")
    assert result.harness.strip() == "{}"
    assert result.telemetry["operational_retries"] == 2 and result.telemetry["context_reduced"] is False


def test_client_shrinks_the_user_prompt_on_context_overflow_when_enabled(monkeypatch) -> None:
    from research_pipeline.llm.failure_policy import FailurePolicy

    monkeypatch.setattr("research_pipeline.llm.failure_policy.time.sleep", lambda s: None)
    client = _client(FailurePolicy(retries=1, reduce_context=True))
    sizes = []

    def post(payload):
        sizes.append(len(payload["messages"][1]["content"]))
        if len(sizes) == 1:
            raise RuntimeError("This model's maximum context length is 8192 tokens")
        return {"choices": [{"message": {"content": "ok"}}]}

    client._post_json = post
    result = client.complete("S", "u" * 10000)
    assert sizes[1] < sizes[0] and result.telemetry["context_reduced"] is True


def test_client_retries_an_api_timeout_reported_as_runtime_error(monkeypatch) -> None:
    from research_pipeline.llm.failure_policy import FailurePolicy

    monkeypatch.setattr("research_pipeline.llm.failure_policy.time.sleep", lambda s: None)
    client = _client(FailurePolicy(retries=1))
    answers = [RuntimeError("Timeout ao chamar OpenAI Responses API."), {"choices": [{"message": {"content": "ok"}}]}]

    def post(payload):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    client._post_json = post
    assert client.complete("S", "U").telemetry["operational_retries"] == 1


def test_client_does_not_retry_after_the_call_deadline(monkeypatch) -> None:
    from research_pipeline.llm.failure_policy import DeadlineExceeded, FailurePolicy

    monkeypatch.setattr("research_pipeline.llm.failure_policy.time.sleep", lambda s: None)
    client = _client(FailurePolicy(retries=3))
    calls = []

    def post(payload):
        calls.append(1)
        raise TimeoutError("LLM call deadline exceeded")

    client._post_json = post
    with pytest.raises(DeadlineExceeded):
        client.complete("S", "U")
    assert len(calls) == 1
