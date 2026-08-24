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
