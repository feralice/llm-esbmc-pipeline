"""One policy for operational failures of an LLM call: retry with a fixed wait, shrink an oversized prompt.

Deterministic on purpose (no jitter, fixed shrink rule), so a run can be reproduced from its recorded settings.
A policy changes how a call is delivered, never what is asked: it is off by default (``retries=0``).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from .rate_limit import UsageLimitReached

SHRINK_FACTOR = 2


class EmptyResponse(RuntimeError):
    """The provider answered with no text."""


class DeadlineExceeded(TimeoutError):
    """The caller's total time budget is spent: retrying cannot help."""


_TRANSIENT = re.compile(r"Timeout ao chamar|Falha de rede", re.IGNORECASE)


def as_transient(exc: Exception) -> TimeoutError | None:
    """A timeout or network failure the providers report as RuntimeError, as a TimeoutError; None otherwise."""
    if isinstance(exc, TimeoutError):
        return exc
    if isinstance(exc, RuntimeError) and not isinstance(exc, UsageLimitReached) and _TRANSIENT.search(str(exc)):
        return TimeoutError(str(exc))
    return None


class ContextOverflow(RuntimeError):
    """The prompt does not fit in the model's context window."""


@dataclass(frozen=True)
class FailurePolicy:
    retries: int = 0
    base_delay: float = 2.0
    reduce_context: bool = False

    def as_config(self) -> dict:
        return {"retries": self.retries, "base_delay": self.base_delay, "reduce_context": self.reduce_context}


@dataclass(frozen=True)
class Outcome:
    value: object
    retries: int = 0
    context_reduced: bool = False


def _reduced(prompt: str) -> str:
    """Keep the head and the tail, drop the middle, with a visible marker."""
    marker = "\n[PROMPT_REDUCED_AFTER_CONTEXT_OVERFLOW]\n"
    keep = max(len(prompt) // SHRINK_FACTOR - len(marker), 0)
    head = keep * 3 // 4
    return prompt[:head] + marker + (prompt[-(keep - head):] if keep > head else "")


def run_with_policy(call: Callable[[str], object], prompt: str, policy: FailurePolicy, *,
                    sleep: Callable[[float], None] | None = None) -> Outcome:
    """Run ``call(prompt)``; transient failures are retried up to ``policy.retries`` times.

    A usage limit is never retried: it ends the batch and the run resumes from its checkpoint.
    """
    wait = sleep or time.sleep
    retries, reduced = 0, False
    while True:
        try:
            return Outcome(call(prompt), retries, reduced)
        except (UsageLimitReached, DeadlineExceeded):
            raise
        except ContextOverflow:
            if not policy.reduce_context or retries >= policy.retries:
                raise
            prompt, reduced = _reduced(prompt), True
        except (TimeoutError, EmptyResponse):
            if retries >= policy.retries:
                raise
        wait(policy.base_delay * 2 ** retries)
        retries += 1


class RetryingAnalyzer:
    """Detection analyzer under a policy: timeouts and network failures are retried (the prompt is built inside the
    analyzer, so context reduction does not apply); every other attribute is the inner analyzer's."""

    def __init__(self, inner, policy: FailurePolicy) -> None:
        self._inner, self._policy = inner, policy

    def analyze(self, unit):
        def attempt(_: str):
            try:
                return self._inner.analyze(unit)
            except RuntimeError as exc:
                transient = as_transient(exc)
                if transient is None:
                    raise
                raise transient from exc

        return run_with_policy(attempt, "", self._policy).value

    def __getattr__(self, name: str):
        return getattr(self._inner, name)
