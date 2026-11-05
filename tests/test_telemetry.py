from research_pipeline.llm.pricing import call_cost, total_cost
from research_pipeline.llm.telemetry import response_event


def test_response_event_normalizes_provider_usage() -> None:
    event = response_event(
        provider="anthropic",
        requested_model="model-a",
        duration_seconds=1.25,
        response={"model": "snapshot-a", "usage": {"input_tokens": 10, "output_tokens": 4}},
    )
    assert event["total_tokens"] == 14
    assert event["returned_model"] == "snapshot-a"
    assert event["status"] == "success"


def test_response_event_reads_openai_responses_cache_field() -> None:
    event = response_event(
        provider="openai",
        requested_model="gpt-4o-mini",
        duration_seconds=1.0,
        response={
            "model": "gpt-4o-mini-2024-07-18",
            "usage": {
                "input_tokens": 2000,
                "input_tokens_details": {"cached_tokens": 1536},
                "output_tokens": 100,
                "total_tokens": 2100,
            },
        },
    )
    assert event["cached_tokens"] == 1536


def test_response_event_reads_chat_completions_cache_field() -> None:
    event = response_event(
        provider="ollama",
        requested_model="qwen2.5-coder",
        duration_seconds=1.0,
        response={
            "usage": {
                "prompt_tokens": 2000,
                "prompt_tokens_details": {"cached_tokens": 0},
                "completion_tokens": 100,
            },
        },
    )
    assert event["cached_tokens"] == 0


def test_response_event_cached_tokens_absent_when_provider_omits_it() -> None:
    event = response_event(
        provider="codex",
        requested_model="",
        duration_seconds=1.0,
        response={"usage": {"input_tokens": 2000, "output_tokens": 100}},
    )
    assert event["cached_tokens"] is None


def test_anthropic_call_is_priced_from_the_model_table() -> None:
    event = response_event(
        provider="anthropic", requested_model="claude-sonnet-5-5", duration_seconds=1.0,
        response={"model": "claude-sonnet-5-5", "usage": {"input_tokens": 1_000_000, "output_tokens": 100_000}},
    )
    assert event["cost_usd"] == 2.0 + 1.0
    assert event["billing"] == "api"


def test_anthropic_cache_tokens_are_priced_apart() -> None:
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 1_000_000,
             "cache_creation": {"ephemeral_5m_input_tokens": 1_000_000, "ephemeral_1h_input_tokens": 1_000_000}}
    assert call_cost("anthropic", "claude-opus-5-5", usage) == 0.20 + 1.25 * 4.0 + 2 * 4.0


def test_a_dated_snapshot_takes_its_model_price() -> None:
    assert call_cost("anthropic", "claude-haiku-4-5-20251001", {"input_tokens": 1_000_000, "output_tokens": 0}) == 1.0


def test_an_unknown_model_has_no_cost_not_zero() -> None:
    event = response_event(
        provider="anthropic", requested_model="claude-unknown-9", duration_seconds=1.0,
        response={"usage": {"input_tokens": 10, "output_tokens": 4}},
    )
    assert event["cost_usd"] is None


def test_a_failed_anthropic_call_has_no_cost() -> None:
    event = response_event(provider="anthropic", requested_model="claude-sonnet-5-5", duration_seconds=1.0,
                           error=RuntimeError("boom"))
    assert event["cost_usd"] is None


def test_the_claude_cli_subscription_costs_nothing_per_call() -> None:
    event = response_event(provider="claude_cli", requested_model="sonnet", duration_seconds=1.0,
                           response={"usage": {"input_tokens": 10, "output_tokens": 4}})
    assert event["cost_usd"] == 0.0
    assert event["billing"] == "assinatura"


def test_other_api_providers_are_not_priced() -> None:
    event = response_event(provider="openai", requested_model="gpt-4o-mini", duration_seconds=1.0,
                           response={"usage": {"input_tokens": 10, "output_tokens": 4}})
    assert event["cost_usd"] is None and event["billing"] is None


def test_total_cost_is_unknown_when_no_call_was_priced() -> None:
    assert total_cost([{"cost_usd": None}, {}]) is None
    assert total_cost([{"cost_usd": 0.5}, {"cost_usd": None}, {"cost_usd": 0.25}]) == 0.75
