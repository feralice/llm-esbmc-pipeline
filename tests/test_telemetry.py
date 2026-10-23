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
