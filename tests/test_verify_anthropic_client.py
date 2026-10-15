import io
import json

import pytest

from research_pipeline.verify import llm_client
from research_pipeline.verify.llm_client import LLMClient


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _reply(payload: dict):
    seen = {}

    def urlopen(req, timeout):
        seen["url"], seen["headers"], seen["body"] = req.full_url, dict(req.header_items()), json.loads(req.data)
        return _Response(json.dumps(payload).encode())
    return urlopen, seen


def test_anthropic_backend_sends_a_messages_request_and_reads_text_and_usage(monkeypatch):
    urlopen, seen = _reply({"content": [{"type": "text", "text": '```json\n{"params": {}}\n```'}],
                            "stop_reason": "end_turn", "model": "claude-sonnet-5-5",
                            "usage": {"input_tokens": 10, "output_tokens": 5}})
    monkeypatch.setattr(llm_client.request, "urlopen", urlopen)
    client = LLMClient(backend="anthropic", model="claude-sonnet-5-5", api_key="k")
    result = client.complete("system text", "user text", json_mode=True)
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["X-api-key"] == "k"
    assert seen["body"]["system"] == "system text"
    assert seen["body"]["messages"] == [{"role": "user", "content": "user text"}]
    assert result.harness.strip() == '{"params": {}}'
    assert result.telemetry["total_tokens"] == 15


def test_anthropic_reply_cut_at_max_tokens_is_an_error_not_a_partial_spec(monkeypatch):
    urlopen, _ = _reply({"content": [{"type": "text", "text": '{"params": '}], "stop_reason": "max_tokens"})
    monkeypatch.setattr(llm_client.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="max_tokens"):
        LLMClient(backend="anthropic", model="m", api_key="k").complete("s", "u")


def test_anthropic_backend_needs_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        LLMClient(backend="anthropic", model="m")
