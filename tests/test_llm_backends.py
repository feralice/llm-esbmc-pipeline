"""Tests for `build_analyzer` backend wiring and `ChatCompletionsAnalyzer`.

The "google" backend (added alongside OpenAI) reuses `ChatCompletionsAnalyzer`
with a swapped base_url instead of its own client, so both the wiring in
`factory.py` and the shared HTTP path in `chat_completions.py` need direct
coverage -- neither had any before this file. No network call is made; the
Gemini API is unreachable from unit tests without GEMINI_API_KEY, so hitting
it for real belongs under the `live_llm` marker, not here.
"""

from __future__ import annotations

import json
from io import BytesIO
from urllib import error

import pytest

from research_pipeline.llm.backends.chat_completions import ChatCompletionsAnalyzer
from research_pipeline.llm.backends.factory import (
    _DEFAULT_OLLAMA_URL,
    _GEMINI_OPENAI_BASE_URL,
    build_analyzer,
)
from research_pipeline.models import CodeUnit


def _unit() -> CodeUnit:
    return CodeUnit(
        path=None, name="f", qualname="f", source="def f(): pass\n",
        start_line=1, end_line=1, parameters=[], type_hints={},
        operations=[], loops=[], conditionals=[], guards=[], metrics={},
    )


# --- factory wiring ----------------------------------------------------------


def test_google_backend_uses_gemini_compatible_endpoint():
    analyzer = build_analyzer(backend="google", google_api_key="secret")
    assert isinstance(analyzer, ChatCompletionsAnalyzer)
    assert analyzer.base_url == _GEMINI_OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
    assert analyzer.model == "gemini-2.5-flash"
    assert analyzer.api_key == "secret"


def test_google_backend_defaults_api_key_to_empty_string_not_none():
    # ChatCompletionsAnalyzer._post_json always formats
    # f"Bearer {self.api_key}" -- a None here would send "Bearer None"
    # instead of failing loudly when GEMINI_API_KEY is unset.
    analyzer = build_analyzer(backend="google", google_api_key=None)
    assert analyzer.api_key == ""


def test_google_backend_throttles_between_calls():
    # Gemini's free tier rate-limits aggressively; ollama (local) does not.
    assert build_analyzer(backend="google", google_api_key="k").request_delay == 4.0
    assert build_analyzer(backend="ollama").request_delay == 0.0


def test_google_backend_model_override():
    analyzer = build_analyzer(backend="google", llm_model="gemini-2.0-pro", google_api_key="k")
    assert analyzer.model == "gemini-2.0-pro"


def test_ollama_backend_uses_local_default_url():
    analyzer = build_analyzer(backend="ollama")
    assert analyzer.base_url == _DEFAULT_OLLAMA_URL.rstrip("/") + "/chat/completions"


def test_unknown_backend_rejected():
    with pytest.raises(ValueError, match="Backend desconhecido"):
        build_analyzer(backend="not-a-backend")


# --- ChatCompletionsAnalyzer.analyze: shared by ollama and google -----------


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _openai_shaped_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_analyze_happy_path_parses_findings(monkeypatch):
    findings_json = json.dumps({"findings": [{
        "id": "f1", "category": "division_by_zero", "verifiable": True,
        "confidence": "high", "title": "t", "explanation": "e", "evidence": [],
    }]})
    response = _FakeHTTPResponse(_openai_shaped_response(findings_json))
    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.request.urlopen",
        lambda *a, **k: response,
    )
    analyzer = ChatCompletionsAnalyzer(api_key="k")
    findings = analyzer.analyze(_unit())
    assert len(findings) == 1
    assert findings[0].id == "f1"
    assert len(analyzer.telemetry_events) == 1


def test_analyze_malformed_content_returns_no_findings_not_an_exception(monkeypatch):
    response = _FakeHTTPResponse(_openai_shaped_response("not json at all"))
    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.request.urlopen",
        lambda *a, **k: response,
    )
    analyzer = ChatCompletionsAnalyzer(api_key="k")
    assert analyzer.analyze(_unit()) == []


def test_post_json_retries_on_server_error_then_succeeds(monkeypatch):
    calls = {"n": 0}
    ok_response = _FakeHTTPResponse(_openai_shaped_response(json.dumps({"findings": []})))

    def _urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise error.HTTPError(req.full_url, 503, "unavailable", {}, BytesIO(b""))
        return ok_response

    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.request.urlopen", _urlopen,
    )
    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.time.sleep", lambda _s: None,
    )
    analyzer = ChatCompletionsAnalyzer(api_key="k")
    assert analyzer.analyze(_unit()) == []
    assert calls["n"] == 2


def test_post_json_gives_up_after_exhausting_retries(monkeypatch):
    def _always_fails(req, timeout):
        raise error.HTTPError(req.full_url, 500, "boom", {}, BytesIO(b"details"))

    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.request.urlopen", _always_fails,
    )
    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.time.sleep", lambda _s: None,
    )
    analyzer = ChatCompletionsAnalyzer(api_key="k")
    with pytest.raises(RuntimeError, match="500"):
        analyzer.analyze(_unit())


def test_post_json_url_error_gives_ollama_hint_for_local_backend(monkeypatch):
    def _refused(req, timeout):
        raise error.URLError("connection refused")

    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.request.urlopen", _refused,
    )
    analyzer = ChatCompletionsAnalyzer(api_key="k", base_url="http://localhost:11434/v1")
    with pytest.raises(RuntimeError, match="ollama serve"):
        analyzer.analyze(_unit())


def test_post_json_url_error_omits_ollama_hint_for_gemini_backend(monkeypatch):
    # Regression: a network failure calling Gemini used to unconditionally
    # tell the user to run `ollama serve`, which is wrong advice for a
    # cloud backend and was never actually the fix for the failure.
    def _refused(req, timeout):
        raise error.URLError("name resolution failed")

    monkeypatch.setattr(
        "research_pipeline.llm.backends.chat_completions.request.urlopen", _refused,
    )
    analyzer = ChatCompletionsAnalyzer(api_key="k", base_url=_GEMINI_OPENAI_BASE_URL)
    with pytest.raises(RuntimeError) as excinfo:
        analyzer.analyze(_unit())
    assert "ollama" not in str(excinfo.value).lower()
