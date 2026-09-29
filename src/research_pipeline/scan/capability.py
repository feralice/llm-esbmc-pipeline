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


# Typical fixes, in the order checked; each names a construct the rewrite may change.
_FIX_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Return type undefined", re.IGNORECASE),
     "Add a return annotation (-> T, or -> None) to every function and method in the module."),
    (re.compile(r"not a @staticmethod", re.IGNORECASE),
     "Call the method through an instance in main(): obj = ClassName() then obj.method(...)."),
    (re.compile(r'(?:Object|Function) "[^"]+" not found|not defined|NameError', re.IGNORECASE),
     "That name is not modeled by ESBMC-Python or is missing from the module. Do not invent helpers. "
     "If it is a library call, replace only that call with an equivalent pure-Python expression in place; "
     "if no equivalent exists, return the same rewrite unchanged."),
    (re.compile(r"list indices must be integers|Cannot unpack|DictComp|ListComp", re.IGNORECASE),
     "Give every list/dict parameter a precise element type (for example list[dict[str, int]] instead of "
     "list) and build the driver input as a literal container of that exact shape with nondet leaves."),
    (re.compile(r"Type inference failed|Could not resolve type", re.IGNORECASE),
     "Annotate every parameter and every local whose type ESBMC cannot infer."),
    (re.compile(r"unsupported|not supported|GeneratorExp", re.IGNORECASE),
     "Replace the unsupported construct with an equivalent supported one (an explicit loop instead of a "
     "generator or comprehension, str concatenation instead of % formatting)."),
)


def fix_hint(diagnostic: CapabilityDiagnostic) -> str:
    """Typical fix for a conversion failure, for the rewrite feedback prompt."""
    for pattern, hint in _FIX_HINTS:
        if pattern.search(diagnostic.message):
            return hint
    return ""
