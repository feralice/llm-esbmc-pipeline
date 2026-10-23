from __future__ import annotations


def response_event(
    *,
    provider: str,
    requested_model: str,
    duration_seconds: float,
    response: dict | None = None,
    error: Exception | None = None,
) -> dict:
    """Normalize one provider call without assuming every provider reports usage."""
    usage = response.get("usage", {}) if isinstance(response, dict) else {}
    prompt = _first_int(usage, "prompt_tokens", "input_tokens")
    completion = _first_int(usage, "completion_tokens", "output_tokens")
    total = _first_int(usage, "total_tokens")
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    cached = _cached_tokens(usage)
    message = str(error) if error else ""
    return {
        "provider": provider,
        "requested_model": requested_model,
        "returned_model": response.get("model") if isinstance(response, dict) else None,
        "status": "timeout" if error and "timeout" in message.lower() else ("error" if error else "success"),
        "duration_seconds": round(duration_seconds, 6),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_tokens": cached,
        "error": message or None,
    }


def _cached_tokens(usage: dict) -> int | None:
    """Read the provider's automatic prompt-cache hit count, when reported.

    OpenAI's Responses API nests it under ``input_tokens_details.cached_tokens``;
    the Chat Completions API (used for the Ollama-compatible backend) nests it
    under ``prompt_tokens_details.cached_tokens``. Ollama itself never sets it —
    there is no server-side cache to report, so the field stays None, distinct
    from a real zero-hit call.
    """
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

