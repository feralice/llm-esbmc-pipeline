from research_pipeline.llm.pricing import call_cost, total_cost
from research_pipeline.llm.rate_limit import UsageLimitReached
from research_pipeline.llm.telemetry import response_event
from research_pipeline.llm.usage_summary import summarize


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


def test_claude_cli_keeps_the_cost_the_cli_reported_and_bills_nothing_per_token() -> None:
    event = response_event(provider="claude_cli", requested_model="sonnet", duration_seconds=1.0,
                           response={"model": "sonnet", "reported_cost_usd": 0.0123,
                                     "usage": {"input_tokens": 10, "output_tokens": 4}})
    assert event["cost_usd"] == 0.0123
    assert event["cost_source"] == "cli_reported"
    assert event["billed_usd"] is None
    assert event["billing"] == "assinatura"


def test_claude_cli_without_a_reported_cost_or_known_model_has_unknown_cost_not_zero() -> None:
    event = response_event(provider="claude_cli", requested_model="sonnet", duration_seconds=1.0,
                           response={"model": "sonnet", "usage": {"input_tokens": 10, "output_tokens": 4}})
    assert event["cost_usd"] is None
    assert event["cost_source"] is None


def test_claude_cli_prices_a_known_model_as_an_estimate_when_the_cli_omits_its_cost() -> None:
    event = response_event(provider="claude_cli", requested_model="claude-sonnet-5-5", duration_seconds=1.0,
                           response={"model": "claude-sonnet-5-5",
                                     "usage": {"input_tokens": 1_000_000, "output_tokens": 100_000}})
    assert event["cost_usd"] == 2.0 + 1.0
    assert event["cost_source"] == "estimated"
    assert event["billed_usd"] is None


def test_claude_cli_prompt_total_includes_cache_writes_and_reads() -> None:
    event = response_event(
        provider="claude_cli", requested_model="sonnet", duration_seconds=1.0,
        response={"model": "sonnet", "usage": {
            "input_tokens": 6, "output_tokens": 879,
            "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 50_000,
        }},
    )
    assert event["prompt_tokens"] == 51_006
    assert event["cached_tokens"] == 50_000
    assert event["cache_creation_tokens"] == 1000
    assert event["total_tokens"] == 51_006 + 879


def test_api_calls_are_billed_at_the_estimate() -> None:
    event = response_event(provider="anthropic", requested_model="claude-sonnet-5-5", duration_seconds=1.0,
                           response={"model": "claude-sonnet-5-5", "usage": {"input_tokens": 1_000_000, "output_tokens": 0}})
    assert event["cost_source"] == "estimated"
    assert event["billed_usd"] == event["cost_usd"] == 2.0


def test_usage_limit_and_timeout_are_classified_apart_from_other_errors() -> None:
    limit = response_event(provider="claude_cli", requested_model="sonnet", duration_seconds=1.0,
                           error=UsageLimitReached("You've hit your 5-hour limit"))
    timeout = response_event(provider="claude_cli", requested_model="sonnet", duration_seconds=1.0,
                             error=TimeoutError("Timeout ao chamar claude -p."))
    other = response_event(provider="claude_cli", requested_model="sonnet", duration_seconds=1.0,
                           error=RuntimeError("JSON inválido"))
    assert (limit["status"], limit["error_kind"]) == ("error", "usage_limit")
    assert (timeout["status"], timeout["error_kind"]) == ("timeout", "timeout")
    assert (other["status"], other["error_kind"]) == ("error", "error")


def test_other_api_providers_are_not_priced() -> None:
    event = response_event(provider="openai", requested_model="gpt-4o-mini", duration_seconds=1.0,
                           response={"usage": {"input_tokens": 10, "output_tokens": 4}})
    assert event["cost_usd"] is None and event["billing"] is None


def test_total_cost_is_unknown_when_no_call_was_priced() -> None:
    assert total_cost([{"cost_usd": None}, {}]) is None
    assert total_cost([{"cost_usd": 0.5}, {"cost_usd": None}, {"cost_usd": 0.25}]) == 0.75


def test_summary_counts_unknown_costs_and_tokens_apart_from_zero() -> None:
    rows = [
        {"provider": "claude_cli", "requested_model": "sonnet", "stage": "detection", "status": "success",
         "prompt_tokens": 10, "completion_tokens": 5, "cost_usd": 0.5, "cost_source": "cli_reported", "billed_usd": None},
        {"provider": "claude_cli", "requested_model": "sonnet", "stage": "detection", "status": "error",
         "error_kind": "usage_limit", "prompt_tokens": None, "completion_tokens": None, "cost_usd": None},
    ]
    (group,) = summarize(rows)
    assert group["calls"] == 2
    assert group["usage_limit"] == 1
    assert group["unknown_prompt"] == 1
    assert group["costed"] == 1
    assert group["cost_usd"] == 0.5


def test_rows_written_before_cost_source_are_unknown_cost_not_the_old_zero() -> None:
    (group,) = summarize([{"provider": "claude_cli", "requested_model": "sonnet", "stage": "synthesis",
                           "status": "success", "prompt_tokens": 6, "completion_tokens": 9, "cost_usd": 0.0}])
    assert group["legacy"] == 1
    assert group["costed"] == 0
    assert group["cost_usd"] == 0.0


def test_legacy_errors_are_classified_from_their_message() -> None:
    rows = [
        {"provider": "claude_cli", "requested_model": "sonnet", "stage": "synthesis", "status": "error",
         "error": "claude -p saiu com código 1: You've hit your 5-hour limit"},
        {"provider": "claude_cli", "requested_model": "sonnet", "stage": "synthesis", "status": "timeout",
         "error": "Timeout ao chamar claude -p."},
        {"provider": "claude_cli", "requested_model": "sonnet", "stage": "synthesis", "status": "error",
         "error": "JSON inválido"},
    ]
    (group,) = summarize(rows)
    assert (group["usage_limit"], group["timeout"]) == (1, 1)


def test_legacy_api_rows_keep_their_stored_cost() -> None:
    (group,) = summarize([{"provider": "anthropic", "requested_model": "claude-sonnet-5-5", "stage": "synthesis",
                           "status": "success", "prompt_tokens": 10, "completion_tokens": 4, "cost_usd": 0.0045}])
    assert group["costed"] == 1
    assert group["cost_usd"] == 0.0045
