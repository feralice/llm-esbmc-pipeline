"""US$ cost of one LLM call from its reported token usage.

Anthropic first-party API list prices per million tokens, from the claude-api skill's model table (cached
2026-10-06): input, output and cache read. A 5-minute cache write costs 1.25x input and a 1-hour write 2x.
Claude Haiku 5.5 is priced at its tier for prompts up to 100K tokens.
"""

from __future__ import annotations

import re

ANTHROPIC_PRICES: dict[str, tuple[float, float, float]] = {
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-mythos-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
    "claude-mythos-5": (10.00, 50.00, 1.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-opus-4-7": (5.00, 25.00, 0.50),
    "claude-opus-4-6": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}
# Billed by the plan the CLI is logged into, not per token.
SUBSCRIPTION_PROVIDERS = frozenset({"claude_cli", "codex"})
SUBSCRIPTION = "assinatura"

_DATE_SUFFIX = re.compile(r"-\d{8}$")


def billing(provider: str) -> str | None:
    if provider in SUBSCRIPTION_PROVIDERS:
        return SUBSCRIPTION
    return "api" if provider == "anthropic" else None


def call_cost(provider: str, model: str | None, usage: dict) -> float | None:
    """0.0 for a subscription CLI; for the Anthropic API, the list price of ``usage``; None when the price is
    unknown (another provider, a model missing from the table, or no token counts), never a guessed 0."""
    if provider in SUBSCRIPTION_PROVIDERS:
        return 0.0
    if provider != "anthropic":
        return None
    price = ANTHROPIC_PRICES.get(_DATE_SUFFIX.sub("", model or ""))
    tokens_in, tokens_out = usage.get("input_tokens"), usage.get("output_tokens")
    if price is None or not isinstance(tokens_in, int) or not isinstance(tokens_out, int):
        return None
    per_in, per_out, per_read = price
    split = usage.get("cache_creation")
    if isinstance(split, dict):
        written = 1.25 * (split.get("ephemeral_5m_input_tokens") or 0) + 2 * (split.get("ephemeral_1h_input_tokens") or 0)
    else:
        written = 1.25 * (usage.get("cache_creation_input_tokens") or 0)
    read = usage.get("cache_read_input_tokens") or 0
    return round((tokens_in * per_in + written * per_in + read * per_read + tokens_out * per_out) / 1_000_000, 6)


def total_cost(events: list[dict]) -> float | None:
    """Sum of the priced calls; None when no call had a price."""
    costs = [e["cost_usd"] for e in events if isinstance(e.get("cost_usd"), (int, float))]
    return round(sum(costs), 6) if costs else None
