import json

from research_pipeline.llm.telemetry import (
    response_event,
    summarize_esbmc_records,
    summarize_events,
    write_telemetry,
)


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


def test_summary_reports_cache_hit_rate() -> None:
    events = [
        {"status": "success", "duration_seconds": 1.0, "total_tokens": 12,
         "prompt_tokens": 10, "cached_tokens": 8},
        {"status": "success", "duration_seconds": 1.0, "total_tokens": 12,
         "prompt_tokens": 10, "cached_tokens": 0},
    ]
    summary = summarize_events(events)
    assert summary["calls_with_cache_data"] == 2
    assert summary["cached_tokens"] == 8
    assert summary["cache_hit_rate"] == 0.4


def test_summary_cache_hit_rate_is_none_when_no_provider_reports_it() -> None:
    events = [{"status": "success", "duration_seconds": 1.0, "total_tokens": 12}]
    summary = summarize_events(events)
    assert summary["calls_with_cache_data"] == 0
    assert summary["cached_tokens"] is None
    assert summary["cache_hit_rate"] is None


def test_summary_distinguishes_missing_usage_and_timeouts() -> None:
    events = [
        {"status": "success", "duration_seconds": 1.0, "total_tokens": 12},
        {"status": "timeout", "duration_seconds": 3.0, "total_tokens": None},
    ]
    summary = summarize_events(events)
    assert summary["calls"] == 2
    assert summary["timeouts"] == 1
    assert summary["calls_with_token_usage"] == 1
    assert summary["total_tokens"] == 12
    assert summary["latency_seconds"]["median"] == 2.0


def test_write_telemetry_writes_events_and_summary(tmp_path) -> None:
    output = write_telemetry([], tmp_path / "telemetry.json")
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["calls"] == 0
    assert payload["summary"]["total_tokens"] is None


def test_esbmc_summary_separates_statuses_and_missing_times() -> None:
    summary = summarize_esbmc_records([
        {"status": "violation_found", "time_seconds": 1.5},
        {"status": "timeout", "time_seconds": 30},
        {"status": "tool_error"},
    ])
    assert summary["executions"] == 3
    assert summary["executions_with_time"] == 2
    assert summary["statuses"]["timeout"] == 1
