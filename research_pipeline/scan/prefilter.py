"""Step 1 of the scan mode: cheap AST pre-filter.

A real repository has far too many functions to send every one to the LLM.
This module keeps only the functions that contain an operation whose safety
depends on an unchecked numeric value: an integer division / modulo, a
sequence subscript, a `divmod()` / `.pop()` / `.insert()` call, or a
`range()` over a non-literal argument.

Pure AST + regex. No LLM, no ESBMC, no network. The decision is deliberately
permissive: a false keep only costs one LLM triage call downstream, a false
drop silently loses a candidate, so the signals err toward keeping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import CodeUnit

# Method calls that index or size a sequence by a positional argument without
# going through a Subscript node. Kept in sync with ast_utils._OOB_METHOD_NAMES.
_POSITIONAL_METHOD_NAMES = frozenset({"pop", "insert"})

# Source-level patterns that preprocess.py does not record as an OperationRecord
# but that still mark a value-dependent operation.
_SOURCE_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("divmod_call", re.compile(r"\bdivmod\s*\(")),
    # range() whose first (or only) argument is not a plain integer literal:
    # range(n), range(len(x)), range(a, b) ... but not range(3) / range(0, 10).
    ("range_over_value", re.compile(r"\brange\s*\(\s*(?![\d\s,)])")),
    # subscript with an offset index, e.g. xs[i - 1], data[n + 1]
    ("offset_index", re.compile(r"\[[^\]]*[+-]\s*\d+\s*\]")),
)


@dataclass
class RiskAssessment:
    """Why (or why not) a CodeUnit is worth sending to the LLM."""

    is_risky: bool
    signals: list[str] = field(default_factory=list)


def assess_unit(unit: CodeUnit) -> RiskAssessment:
    """Return a RiskAssessment for one function.

    A unit is risky when it carries at least one value-dependent operation.
    """
    signals: list[str] = []

    for operation in unit.operations:
        if operation.kind == "division":
            signals.append("division_or_modulo")
        elif operation.kind == "subscript":
            signals.append("subscript")
        elif operation.kind == "call":
            head = operation.expression.split("(", 1)[0]
            name = head.rsplit(".", 1)[-1]
            if name == "divmod" or name in _POSITIONAL_METHOD_NAMES:
                signals.append(f"call_{name}")

    for label, pattern in _SOURCE_SIGNALS:
        if pattern.search(unit.source):
            signals.append(label)

    # De-duplicate while keeping first-seen order, for a stable report.
    seen: dict[str, None] = {}
    for signal in signals:
        seen.setdefault(signal, None)
    ordered = list(seen)

    return RiskAssessment(is_risky=bool(ordered), signals=ordered)


def filter_units(
    units: list[CodeUnit], *, mode: str = "risky"
) -> list[tuple[CodeUnit, RiskAssessment]]:
    """Filter a list of CodeUnits for the scan pipeline.

    mode="risky" (default): keep only units with at least one risk signal.
    mode="all": keep every unit, still attaching its RiskAssessment.
    """
    if mode not in ("risky", "all"):
        raise ValueError(f"mode must be 'risky' or 'all', got {mode!r}")

    assessed = [(unit, assess_unit(unit)) for unit in units]
    if mode == "all":
        return assessed
    return [(unit, risk) for unit, risk in assessed if risk.is_risky]
