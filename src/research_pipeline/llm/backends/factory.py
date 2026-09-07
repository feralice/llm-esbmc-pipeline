from __future__ import annotations

from typing import Literal

from ...llm.protocols import LLMAnalyzer
from .anthropic import AnthropicAnalyzer
from .chat_completions import ChatCompletionsAnalyzer
from .codex import CodexAnalyzer
from .openai import OpenAIResponsesAnalyzer

Backend = Literal["openai", "anthropic", "ollama", "google", "codex"]

_DEFAULT_MODEL: dict[str, str] = {
    "openai":    "gpt-5.5",
    "anthropic": "claude-opus-4-8",
    "ollama":    "deepseek-r1:7b",
    "google":    "gemini-2.5-flash",
    "codex":     "",
}

_DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"
_GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def build_analyzer(
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_base_url: str | None = None,
    google_api_key: str | None = None,
    timeout_seconds: int = 300,
) -> LLMAnalyzer:
    model = llm_model or _DEFAULT_MODEL[backend]
    if backend == "openai":
        return OpenAIResponsesAnalyzer(
            api_key=openai_api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    if backend == "anthropic":
        return AnthropicAnalyzer(
            api_key=anthropic_api_key,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    if backend == "ollama":
        return ChatCompletionsAnalyzer(
            base_url=ollama_base_url or _DEFAULT_OLLAMA_URL,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    if backend == "google":
        return ChatCompletionsAnalyzer(
            base_url=_GEMINI_OPENAI_BASE_URL,
            model=model,
            api_key=google_api_key or "",
            timeout_seconds=timeout_seconds,
            request_delay=4.0,
        )
    if backend == "codex":
        return CodexAnalyzer(model=model, timeout_seconds=timeout_seconds)
    raise ValueError(f"Backend desconhecido: {backend!r}. Use 'openai', 'anthropic', 'ollama', 'google' ou 'codex'.")
