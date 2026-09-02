"""Step 1 of the scan mode: cheap AST pre-filter (optional).

A real repository has far too many functions to send every one to the LLM.
This module scores each function for the syntactic markers of the formal bug
categories ESBMC can later confirm, and can drop the ones with no marker at
all.

It is **opt-in**. The scan runs every function through LLM triage by default;
the pre-filter is only worth enabling on a large formal-bug target where the
triage cost matters. It has nothing to say about code smells, whose markers
are not syntactic.

Signals and the category each points at:

* ``division_or_modulo`` / ``divmod_call`` / ``call_divmod``    -> division_by_zero
* ``subscript`` / ``call_pop`` / ``call_insert`` /
  ``range_over_value`` / ``offset_index``                       -> out_of_bounds
* ``arithmetic_growth``                                         -> integer_overflow
* ``assert_property``                                           -> assertion_violation
* ``precondition_guard``                                        -> invalid_precondition

``none_misuse``, ``type_mismatch`` and ``variable_misuse`` have no cheap
syntactic marker (they need flow or type information) and are left to LLM
triage.

Pure AST + regex. No LLM, no ESBMC, no network. The decision is deliberately
permissive: a false keep only costs one LLM triage call downstream, a false
drop silently loses a candidate, so the signals err toward keeping.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field

from ..models import CodeUnit
from .guards import extract_guards

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

# BinOp operators whose result can exceed both operand magnitudes, i.e. a
# candidate for integer_overflow once ESBMC runs with --overflow-check.
_GROWTH_OPS: tuple[type[ast.operator], ...] = (ast.Mult, ast.Pow, ast.LShift)


@dataclass
class RiskAssessment:
    """Why (or why not) a CodeUnit is worth sending to the LLM."""

    is_risky: bool
    signals: list[str] = field(default_factory=list)


def _structural_signals(source: str) -> list[str]:
    """AST-level signals: growth arithmetic and assertions anywhere in the body."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return []

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, _GROWTH_OPS):
            found.append("arithmetic_growth")
        elif isinstance(node, ast.Assert):
            found.append("assert_property")
    return found


def assess_unit(unit: CodeUnit) -> RiskAssessment:
    """Return a RiskAssessment for one function.

    A unit is risky when it carries at least one marker of a formal bug
    category.
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

    signals.extend(_structural_signals(unit.source))

    if any(guard.origin == "raise" for guard in extract_guards(unit.source)):
        signals.append("precondition_guard")

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
