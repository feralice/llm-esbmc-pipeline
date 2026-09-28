from __future__ import annotations

from typing import Literal

from ...llm.protocols import LLMAnalyzer
from .anthropic import AnthropicAnalyzer
from .chat_completions import ChatCompletionsAnalyzer
from .claude_cli import ClaudeCliAnalyzer
from .codex import CodexAnalyzer
from ..staged import TwoStageAnalyzer
from .openai import OpenAIResponsesAnalyzer

Backend = Literal["openai", "anthropic", "ollama", "google", "codex", "claude_cli"]

_DEFAULT_MODEL: dict[str, str] = {
    "openai":     "gpt-5.5",
    "anthropic":  "claude-opus-4-8",
    "ollama":     "deepseek-r1:7b",
    "google":     "gemini-2.5-flash",
    "codex":      "",
    "claude_cli": "",
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
    include_smells: bool = True,
    detection_strategy: str = "single",
    v2_categories: bool = False,
) -> LLMAnalyzer:
    if backend not in _DEFAULT_MODEL:
        raise ValueError(
            f"Backend desconhecido: {backend!r}. Use 'openai', 'anthropic', 'ollama', 'google', 'codex' ou 'claude_cli'."
        )
    model = llm_model or _DEFAULT_MODEL[backend]
    if detection_strategy not in {"single", "two_stage"}:
        raise ValueError(f"Estratégia de detecção desconhecida: {detection_strategy!r}")

    def wrap(analyzer: LLMAnalyzer) -> LLMAnalyzer:
        return TwoStageAnalyzer(analyzer) if detection_strategy == "two_stage" else analyzer

    if backend == "openai":
        return wrap(OpenAIResponsesAnalyzer(
            api_key=openai_api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            include_smells=include_smells,
            v2_categories=v2_categories,
        ))
    if backend == "anthropic":
        return wrap(AnthropicAnalyzer(
            api_key=anthropic_api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            include_smells=include_smells,
            v2_categories=v2_categories,
        ))
    if backend == "ollama":
        return wrap(ChatCompletionsAnalyzer(
            base_url=ollama_base_url or _DEFAULT_OLLAMA_URL,
            model=model,
            timeout_seconds=timeout_seconds,
            include_smells=include_smells,
            v2_categories=v2_categories,
        ))
    if backend == "google":
        return wrap(ChatCompletionsAnalyzer(
            base_url=_GEMINI_OPENAI_BASE_URL,
            model=model,
            api_key=google_api_key or "",
            timeout_seconds=timeout_seconds,
            request_delay=4.0,
            include_smells=include_smells,
            v2_categories=v2_categories,
        ))
    if backend == "codex":
        return wrap(CodexAnalyzer(model=model, timeout_seconds=timeout_seconds, include_smells=include_smells, v2_categories=v2_categories))
    if backend == "claude_cli":
        return wrap(ClaudeCliAnalyzer(model=model, timeout_seconds=timeout_seconds, include_smells=include_smells, v2_categories=v2_categories))
    raise AssertionError(f"unreachable: {backend!r} passed the _DEFAULT_MODEL membership check above")
