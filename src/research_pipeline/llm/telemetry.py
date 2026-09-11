from __future__ import annotations

import json
import statistics
from pathlib import Path


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


def summarize_events(events: list[dict]) -> dict:
    """Summarize calls while keeping missing provider data visibly missing."""
    durations = [float(event["duration_seconds"]) for event in events if event.get("duration_seconds") is not None]
    token_values = [int(event["total_tokens"]) for event in events if event.get("total_tokens") is not None]
    prompt_values = [int(event["prompt_tokens"]) for event in events if event.get("prompt_tokens") is not None]
    cached_values = [int(event["cached_tokens"]) for event in events if event.get("cached_tokens") is not None]
    return {
        "calls": len(events),
        "successful": sum(event.get("status") == "success" for event in events),
        "timeouts": sum(event.get("status") == "timeout" for event in events),
        "errors": sum(event.get("status") == "error" for event in events),
        "calls_with_token_usage": len(token_values),
        "total_tokens": sum(token_values) if token_values else None,
        # None (not 0) when no event reported a cache field at all -- e.g. every
        # call went through Ollama, which never sets it. A real 0 means the
        # provider reported the field and it was a cache miss every time.
        "calls_with_cache_data": len(cached_values),
        "cached_tokens": sum(cached_values) if cached_values else None,
        "prompt_tokens": sum(prompt_values) if prompt_values else None,
        "cache_hit_rate": (
            round(sum(cached_values) / sum(prompt_values), 4)
            if cached_values and prompt_values and sum(prompt_values) > 0
            else None
        ),
        "latency_seconds": _duration_summary(durations),
    }


def summarize_esbmc_records(records: list[dict]) -> dict:
    """Summarize one-record-per-ESBMC-execution artifacts."""
    durations = [
        float(record["time_seconds"])
        for record in records
        if isinstance(record.get("time_seconds"), (int, float))
    ]
    statuses: dict[str, int] = {}
    for record in records:
        status = str(record.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "executions": len(records),
        "executions_with_time": len(durations),
        "statuses": dict(sorted(statuses.items())),
        "time_seconds": _duration_summary(durations),
    }


def write_telemetry(events: list[dict], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summarize_events(events), "events": events}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _first_int(mapping: dict, *keys: str) -> int | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int):
            return value
    return None


def _duration_summary(values: list[float]) -> dict:
    if not values:
        return {"total": None, "mean": None, "median": None, "p95": None}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(0.95 * len(ordered) + 0.999999) - 1))
    return {
        "total": round(sum(values), 6),
        "mean": round(statistics.fmean(values), 6),
        "median": round(statistics.median(values), 6),
        "p95": round(ordered[p95_index], 6),
    }
