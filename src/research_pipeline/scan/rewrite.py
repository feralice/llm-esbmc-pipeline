"""Validated data contract returned by the compatibility rewrite model."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RewriteChange:
    before: str
    after: str
    reason: str


@dataclass(frozen=True)
class RewriteProposal:
    rewritten_source: str
    driver_source: str
    changes: tuple[RewriteChange, ...]
    input_cases: tuple[dict[str, Any], ...]
    assumptions: tuple[str, ...]
    oracle_ref: str | None


_FIELDS = {
    "rewritten_source", "driver_source", "changes", "input_cases",
    "assumptions", "oracle_ref",
}


def _json_payload(raw: str) -> dict[str, Any]:
    content = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL | re.IGNORECASE)
    if fence:
        content = fence.group(1).strip()
    if not content.startswith("{") and "{" in content and "}" in content:
        content = content[content.index("{"):content.rindex("}") + 1]
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        try:
            # Models sometimes emit Python literals (None/True) inside the JSON.
            payload = ast.literal_eval(content)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            raise ValueError(f"rewrite response must be JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("rewrite response JSON must be an object")
    return payload


def parse_rewrite_proposal(raw: str) -> RewriteProposal:
    """Parse the model response and fail closed on missing or malformed fields."""
    payload = _json_payload(raw)
    missing = _FIELDS - payload.keys()
    extra = payload.keys() - _FIELDS
    if missing:
        raise ValueError(f"rewrite response missing field(s): {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"rewrite response has unknown field(s): {', '.join(sorted(extra))}")

    source = payload["rewritten_source"]
    driver = payload["driver_source"]
    if not isinstance(source, str) or not source.strip():
        raise ValueError("rewritten_source must be a non-empty string")
    if not isinstance(driver, str) or not driver.strip():
        raise ValueError("driver_source must be a non-empty string")

    raw_changes = payload["changes"]
    if not isinstance(raw_changes, list):
        raise ValueError("changes must be a list")
    changes: list[RewriteChange] = []
    for index, item in enumerate(raw_changes):
        if not isinstance(item, dict) or set(item) != {"before", "after", "reason"}:
            raise ValueError(f"changes[{index}] must contain before, after, and reason")
        values = (item["before"], item["after"], item["reason"])
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError(f"changes[{index}] values must be non-empty strings")
        changes.append(RewriteChange(*values))

    raw_cases = payload["input_cases"]
    if not isinstance(raw_cases, list):
        raise ValueError("input_cases must be a list")
    cases: list[dict[str, Any]] = []
    for index, case in enumerate(raw_cases):
        if (not isinstance(case, dict) or set(case) != {"args", "kwargs"}
                or not isinstance(case["args"], list)
                or not isinstance(case["kwargs"], dict)
                or any(not isinstance(key, str) for key in case["kwargs"])):
            raise ValueError(f"input_cases[{index}] must contain list args and object kwargs")
        cases.append(case)

    assumptions = payload["assumptions"]
    if (not isinstance(assumptions, list)
            or any(not isinstance(value, str) or not value.strip() for value in assumptions)):
        raise ValueError("assumptions must be a list of non-empty strings")
    oracle_ref = payload["oracle_ref"]
    if oracle_ref is not None and (not isinstance(oracle_ref, str) or not oracle_ref.strip()):
        raise ValueError("oracle_ref must be null or a non-empty string")

    return RewriteProposal(
        rewritten_source=source,
        driver_source=driver,
        changes=tuple(changes),
        input_cases=tuple(cases),
        assumptions=tuple(assumptions),
        oracle_ref=oracle_ref,
    )
