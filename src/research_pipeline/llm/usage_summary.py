"""Totals over saved ``llm_telemetry.json`` files, one row per provider, model and stage.

Unknown values stay unknown: a missing token count or cost is counted apart, never added as zero.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .pricing import SUBSCRIPTION_PROVIDERS
from .rate_limit import is_usage_limit


def load_rows(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return rows if isinstance(rows, list) else []


_TOTALS = ("calls", "success", "usage_limit", "timeout", "retried", "legacy", "unknown_prompt", "prompt_tokens",
           "completion_tokens", "cached_tokens", "cache_creation_tokens", "cost_usd", "costed", "billed_usd")


def _legacy_error_kind(error: str | None) -> str | None:
    if not error:
        return None
    if is_usage_limit(error):
        return "usage_limit"
    return "timeout" if "timeout" in error.lower() else "error"


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = defaultdict(lambda: dict.fromkeys(_TOTALS, 0.0))
    for row in rows:
        key = (row.get("provider"), row.get("requested_model"), row.get("stage"))
        group = groups[key]
        group["calls"] += 1
        group["success"] += row.get("status") == "success"
        kind = row.get("error_kind") or _legacy_error_kind(row.get("error"))
        group["usage_limit"] += kind == "usage_limit"
        group["timeout"] += kind == "timeout"
        group["retried"] += (row.get("attempts") or 1) > 1
        group["unknown_prompt"] += row.get("prompt_tokens") is None
        group["prompt_tokens"] += row.get("prompt_tokens") or 0
        group["completion_tokens"] += row.get("completion_tokens") or 0
        group["cached_tokens"] += row.get("cached_tokens") or 0
        group["cache_creation_tokens"] += row.get("cache_creation_tokens") or 0
        # Rows written before cost_source existed stored 0.0 for subscription calls: unknown, not zero.
        legacy = "cost_source" not in row
        unknown_subscription = legacy and row.get("provider") in SUBSCRIPTION_PROVIDERS
        group["legacy"] += legacy
        cost = None if unknown_subscription else row.get("cost_usd")
        if isinstance(cost, (int, float)):
            group["cost_usd"] += cost
            group["costed"] += 1
        billed = row.get("billed_usd")
        if isinstance(billed, (int, float)):
            group["billed_usd"] += billed
    return [
        {"provider": provider, "model": model, "stage": stage, **dict(group)}
        for (provider, model, stage), group in sorted(groups.items(), key=lambda item: -item[1]["calls"])
    ]
