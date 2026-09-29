"""Classify ESBMC-Python conversion failures for rewrite feedback."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CapabilityDiagnostic:
    kind: str
    message: str
    source_line: int | None = None
    raw_log_path: str = ""


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "method_entry",
        re.compile(r"not a @staticmethod.*receiver is a class instance", re.IGNORECASE | re.DOTALL),
    ),
    ("import", re.compile(r"Cannot open file|No module named|ModuleNotFoundError", re.IGNORECASE)),
    ("dependency", re.compile(r'(?:Object|Function) "[^"]+" not found')),
    ("generator", re.compile(r"GeneratorExp|generator expression", re.IGNORECASE)),
    ("builtin", re.compile(r"Unsupported builtin|builtin.{0,50}not supported|ERROR: unsupported:", re.IGNORECASE)),
    ("container", re.compile(r"ListComp|list indices must be integers|object of this type has no len", re.IGNORECASE)),
    ("annotation", re.compile(r"annotation.{0,50}(unsupported|not supported|cannot)|unsupported.{0,30}annotation", re.IGNORECASE)),
)


def _line_number(output: str) -> int | None:
    match = re.search(r"\.py\s+line\s+(\d+)", output)
    if match is None:
        match = re.search(r"\.py:(\d+)(?::|\b)", output)
    if match is None:
        match = re.search(r"\.py\s+(\d+):", output)
    return int(match.group(1)) if match else None


def _error_message(output: str, summary: str, status: str) -> str:
    if status == "violation_found":
        return summary.strip() or "ESBMC reported a verifier property violation"
    for line in output.splitlines():
        if "ERROR:" in line or "error:" in line.lower():
            return line.strip()
    return summary.strip() or f"ESBMC status: {status}"


def diagnose_esbmc(
    status: str,
    stdout: str,
    stderr: str,
    raw_log_path: str = "",
    *,
    summary: str = "",
) -> CapabilityDiagnostic:
    """Return a conservative capability label based on a failed ESBMC run.

    A verifier finding is deliberately not treated as a conversion failure,
    even when the output lists unrelated runtime properties as PASSED.
    """
    raw = raw_log_path.strip()
    try:
        # The runners summarize stdout/stderr; the converter error lives in the raw log.
        log = Path(raw).read_text(encoding="utf-8", errors="replace") if raw else ""
    except OSError:
        log = ""
    combined = f"{stdout}\n{stderr}\n{log}"
    if status in {"timeout", "inconclusive"} and re.search(r"timeout|time limit|excedeu", f"{summary}\n{combined}", re.IGNORECASE):
        return CapabilityDiagnostic("timeout", summary.strip() or "ESBMC timed out", None, raw)

    message = _error_message(combined, summary, status)
    if status in {"tool_error", "unsupported_case"}:
        for kind, pattern in _PATTERNS:
            if pattern.search(combined):
                return CapabilityDiagnostic(kind, message, _line_number(combined), raw)
    return CapabilityDiagnostic("unknown", message, None, raw)
