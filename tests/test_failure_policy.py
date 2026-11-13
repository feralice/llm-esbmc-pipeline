from __future__ import annotations

import pytest

from research_pipeline.llm.failure_policy import ContextOverflow, EmptyResponse, FailurePolicy, run_with_policy
from research_pipeline.llm.rate_limit import UsageLimitReached


def _flaky(failures: list[Exception], result: str = "ok"):
    queue = list(failures)

    def call(prompt: str) -> str:
        if queue:
            raise queue.pop(0)
        return result

    return call


def test_default_policy_does_not_retry() -> None:
    with pytest.raises(TimeoutError):
        run_with_policy(_flaky([TimeoutError("x")]), "p", FailurePolicy(), sleep=lambda s: None)


def test_transient_errors_are_retried_with_growing_waits() -> None:
    waits: list[float] = []
    outcome = run_with_policy(_flaky([TimeoutError("a"), EmptyResponse("b")]), "p",
                              FailurePolicy(retries=3, base_delay=2), sleep=waits.append)
    assert outcome.value == "ok" and outcome.retries == 2 and not outcome.context_reduced
    assert waits == [2, 4]


def test_retries_stop_at_the_limit_and_raise_the_last_error() -> None:
    with pytest.raises(TimeoutError):
        run_with_policy(_flaky([TimeoutError("a")] * 3), "p", FailurePolicy(retries=2), sleep=lambda s: None)


def test_usage_limit_is_never_retried() -> None:
    calls = []

    def call(prompt: str) -> str:
        calls.append(prompt)
        raise UsageLimitReached("cota")

    with pytest.raises(UsageLimitReached):
        run_with_policy(call, "p", FailurePolicy(retries=5), sleep=lambda s: None)
    assert len(calls) == 1


def test_context_overflow_shrinks_the_prompt_by_a_fixed_rule_when_enabled() -> None:
    seen: list[int] = []

    def call(prompt: str) -> str:
        seen.append(len(prompt))
        if len(prompt) > 5000:
            raise ContextOverflow("prompt is too long")
        return "ok"

    outcome = run_with_policy(call, "x" * 10000, FailurePolicy(retries=1, reduce_context=True), sleep=lambda s: None)
    assert outcome.context_reduced and outcome.retries == 1 and seen[0] == 10000 and seen[1] <= 5000


def test_context_overflow_without_the_option_is_not_retried() -> None:
    with pytest.raises(ContextOverflow):
        run_with_policy(_flaky([ContextOverflow("too long")]), "p", FailurePolicy(retries=3), sleep=lambda s: None)


def test_retrying_analyzer_retries_timeouts_and_passes_attributes_through() -> None:
    from research_pipeline.llm.failure_policy import RetryingAnalyzer

    class Inner:
        telemetry_events = ["e"]
        calls = 0

        def analyze(self, unit):
            Inner.calls += 1
            if Inner.calls == 1:
                raise TimeoutError("t")
            return [unit]

    wrapped = RetryingAnalyzer(Inner(), FailurePolicy(retries=1, base_delay=0))
    assert wrapped.analyze("u") == ["u"] and wrapped.telemetry_events == ["e"] and Inner.calls == 2


def test_a_passed_deadline_is_not_retried() -> None:
    from research_pipeline.llm.failure_policy import DeadlineExceeded

    calls = []

    def call(prompt: str) -> str:
        calls.append(1)
        raise DeadlineExceeded("LLM call deadline exceeded")

    with pytest.raises(DeadlineExceeded):
        run_with_policy(call, "p", FailurePolicy(retries=5), sleep=lambda s: None)
    assert len(calls) == 1


@pytest.mark.parametrize("message", ["Timeout ao chamar OpenAI Responses API.", "Falha de rede ao chamar X: boom"])
def test_api_timeouts_and_network_failures_count_as_transient(message: str) -> None:
    from research_pipeline.llm.failure_policy import as_transient

    assert isinstance(as_transient(RuntimeError(message)), TimeoutError)
    assert as_transient(RuntimeError("HTTP 400 bad request")) is None
    assert as_transient(UsageLimitReached("Falha de rede cota")) is None


def test_retrying_analyzer_also_retries_api_timeouts() -> None:
    from research_pipeline.llm.failure_policy import RetryingAnalyzer

    class Inner:
        calls = 0

        def analyze(self, unit):
            Inner.calls += 1
            if Inner.calls == 1:
                raise RuntimeError("Falha de rede ao chamar Anthropic API: x")
            return ["ok"]

    assert RetryingAnalyzer(Inner(), FailurePolicy(retries=1, base_delay=0)).analyze("u") == ["ok"]
