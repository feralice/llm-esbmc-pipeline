from __future__ import annotations


def is_daily_quota_exhausted(body: str) -> bool:
    """True when a 429 body signals a per-day quota exhaustion, not a per-minute throttle.

    Sleeping and retrying only helps the latter; a daily cap (e.g. Gemini free tier's
    "GenerateRequestsPerDayPerProjectPerModel-FreeTier") won't clear until the next day,
    so retrying just burns the retry budget on a call that cannot succeed.
    """
    lowered = body.lower()
    return "per day" in lowered or "perday" in lowered.replace("_", "").replace("-", "")
