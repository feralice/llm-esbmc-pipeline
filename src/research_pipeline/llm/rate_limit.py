from __future__ import annotations

import re
import sys
from collections.abc import Callable

# Seen in real runs: `claude -p` "You've hit your 5-hour limit · resets 1:30am", codex "You’ve hit your usage
# limit", the older Claude Code "Claude AI usage limit reached"; the APIs' quota and credit errors.
_USAGE_LIMIT = re.compile(r"hit your [\w -]*limit|usage limit|credit balance is too low|insufficient_quota",
                          re.IGNORECASE)


class UsageLimitReached(RuntimeError):
    """The plan or quota behind the LLM ran out: every later call fails the same way until it resets, so a batch
    saves its checkpoint and stops instead of recording each remaining case as an error."""


# Distinct from 2 (interrupted or partial run), so a wrapper script can wait for the limit to reset.
USAGE_LIMIT_EXIT = 3


def is_usage_limit(text: str) -> bool:
    return bool(_USAGE_LIMIT.search(text or ""))


def call_failure(message: str, detail: str) -> RuntimeError:
    """``message`` as UsageLimitReached when ``detail`` says the quota ran out, else as a plain RuntimeError."""
    return (UsageLimitReached if is_usage_limit(detail) else RuntimeError)(message)


def exit_on_usage_limit(main: Callable[[], int]) -> int:
    """For a script whose loop saves each finished case: the limit ends it with a message, not a traceback."""
    try:
        return main()
    except UsageLimitReached as exc:
        print(f"Limite de uso da LLM atingido: {exc}\nExecução parada; o que terminou está salvo. "
              "Rode de novo depois que o limite renovar.", file=sys.stderr)
        return USAGE_LIMIT_EXIT


def is_daily_quota_exhausted(body: str) -> bool:
    """True when a 429 body signals a per-day quota exhaustion, not a per-minute throttle.

    Sleeping and retrying only helps the latter; a daily cap (e.g. Gemini free tier's
    "GenerateRequestsPerDayPerProjectPerModel-FreeTier") won't clear until the next day,
    so retrying just burns the retry budget on a call that cannot succeed.
    """
    lowered = body.lower()
    return "per day" in lowered or "perday" in lowered.replace("_", "").replace("-", "")
