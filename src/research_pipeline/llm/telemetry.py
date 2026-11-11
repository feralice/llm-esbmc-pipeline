from __future__ import annotations

from .pricing import billing, call_cost
from .rate_limit import UsageLimitReached

_ANTHROPIC_CACHE_KEYS = ("cache_creation_input_tokens", "cache_read_input_tokens", "cache_creation")


def response_event(
    *,
    provider: str,
    requested_model: str,
    duration_seconds: float,
    response: dict | None = None,
    error: Exception | None = None,
) -> dict:
    """Normalize one provider call without assuming every provider reports usage.

    ``prompt_tokens`` is the whole input. Anthropic reports cache writes and reads apart from ``input_tokens``,
    so they are added back here; OpenAI already counts its cached tokens inside ``input_tokens``.
    ``cost_usd`` prefers the CLI's own figure (``reported_cost_usd``) over the list-price estimate, and
    ``billed_usd`` is set only for calls charged per token, so a subscription call is never counted as spend.
    """
    usage = response.get("usage", {}) if isinstance(response, dict) else {}
    uncached = _first_int(usage, "prompt_tokens", "input_tokens")
    created = _cache_creation_tokens(usage)
    read = _cached_tokens(usage)
    prompt = uncached
    if prompt is not None and any(key in usage for key in _ANTHROPIC_CACHE_KEYS):
        prompt += (created or 0) + (read or 0)
    completion = _first_int(usage, "completion_tokens", "output_tokens")
    total = _first_int(usage, "total_tokens")
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    returned_model = response.get("model") if isinstance(response, dict) else None
    cost, source = _cost(provider, returned_model or requested_model, usage, response)
    return {
        "provider": provider,
        "requested_model": requested_model,
        "returned_model": returned_model,
        "status": _status(error),
        "error_kind": _error_kind(error),
        "error": str(error) if error else None,
        "duration_seconds": round(duration_seconds, 6),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_tokens": read,
        "cache_creation_tokens": created,
        "cost_usd": cost,
        "cost_source": source,
        "billing": billing(provider),
        "billed_usd": cost if billing(provider) == "api" else None,
    }


def _cost(provider: str, model: str | None, usage: dict, response: dict | None) -> tuple[float | None, str | None]:
    reported = response.get("reported_cost_usd") if isinstance(response, dict) else None
    if isinstance(reported, (int, float)):
        return float(reported), "cli_reported"
    estimate = call_cost(provider, model, usage)
    if estimate is not None:
        return estimate, "estimated"
    return None, None


def _status(error: Exception | None) -> str:
    if error is None:
        return "success"
    return "timeout" if _error_kind(error) == "timeout" else "error"


def _error_kind(error: Exception | None) -> str | None:
    if error is None:
        return None
    if isinstance(error, UsageLimitReached):
        return "usage_limit"
    if isinstance(error, TimeoutError) or "timeout" in str(error).lower():
        return "timeout"
    return "error"


def _cache_creation_tokens(usage: dict) -> int | None:
    if "cache_creation_input_tokens" in usage:
        return _first_int(usage, "cache_creation_input_tokens")
    split = usage.get("cache_creation")
    if isinstance(split, dict):
        return sum(v for v in split.values() if isinstance(v, int))
    return None


def _cached_tokens(usage: dict) -> int | None:
    """Read the provider's prompt-cache hit count, when reported.

    Anthropic reports it as ``cache_read_input_tokens``; OpenAI's Responses API nests it under
    ``input_tokens_details.cached_tokens``, and the Chat Completions API under
    ``prompt_tokens_details.cached_tokens``. Ollama never sets it, so the field stays None, distinct from a
    real zero-hit call.
    """
    if "cache_read_input_tokens" in usage:
        return _first_int(usage, "cache_read_input_tokens")
    for details_key in ("input_tokens_details", "prompt_tokens_details"):
        details = usage.get(details_key)
        if isinstance(details, dict):
            value = details.get("cached_tokens")
            if isinstance(value, int):
                return value
    return None


def _first_int(mapping: dict, *keys: str) -> int | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int):
            return value
    return None
