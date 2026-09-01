"""Step 3 backstop: detect an over-restricted harness by assume-ablation.

When a synthesized harness verifies SUCCESSFUL, that can mean one of two very
different things:

* the modelled expression is genuinely safe, or
* an `__ESBMC_assume` line encodes a bound the real caller never guarantees,
  which cut off the path that reaches the bug.

Ablation tells them apart without any ground truth: drop one `__ESBMC_assume`
at a time, re-run ESBMC, and see whether the verdict flips to FAILED. A line
whose removal exposes a violation was masking the bug -- the harness is
over-restricted and the specific assumption is named.

This module builds the ablated variants and classifies the verdicts. It does
NOT run ESBMC itself: the caller passes a `run` callable, so the logic is unit
-testable and the ESBMC dependency stays in one place (verification/).
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, field

# Verdict strings the caller's `run` callable is expected to return. Kept loose
# on purpose -- anything that is not exactly FAILED is treated as "did not
# reproduce the bug" (SUCCESSFUL, TIMEOUT, OTHER, ...).
FAILED = "FAILED"


@dataclass
class AblatedVariant:
    """One harness with a single `__ESBMC_assume` line removed."""

    assumption: str        # the assume test that was removed, as source
    lineno: int            # 1-based line of the removed call in the original
    source: str            # harness source with that line commented out


@dataclass
class AblationReport:
    """Outcome of ablating every top-level assume in a SUCCESSFUL harness."""

    over_restricted: bool
    masking_assumptions: list[str] = field(default_factory=list)
    per_assumption: dict[str, str] = field(default_factory=dict)  # assumption -> verdict


def _assume_calls(tree: ast.Module) -> list[ast.Call]:
    """Every `__ESBMC_assume(...)` call statement in the module, in source order."""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__ESBMC_assume"
        ):
            calls.append(node)
    calls.sort(key=lambda c: (c.lineno, c.col_offset))
    return calls


def build_variants(harness: str) -> list[AblatedVariant]:
    """Produce one AblatedVariant per `__ESBMC_assume` line in the harness.

    A NaN-guard assume (`x == x`) is skipped: removing it re-admits NaN/Inf and
    would flag a spurious "bug" that only exists for non-real inputs.
    """
    try:
        tree = ast.parse(harness)
    except SyntaxError:
        return []

    lines = harness.splitlines()
    variants: list[AblatedVariant] = []
    for call in _assume_calls(tree):
        arg_src = ast.unparse(call.args[0]) if call.args else ""
        if _is_nan_guard(call):
            continue
        end = getattr(call, "end_lineno", call.lineno)
        ablated = list(lines)
        for i in range(call.lineno - 1, end):
            ablated[i] = "# [ablated] " + ablated[i]
        variants.append(
            AblatedVariant(
                assumption=arg_src,
                lineno=call.lineno,
                source="\n".join(ablated) + "\n",
            )
        )
    return variants


def _is_nan_guard(call: ast.Call) -> bool:
    """True for `__ESBMC_assume(x == x)` / `... and y == y` NaN exclusions."""
    if not call.args:
        return False

    def _all_self_eq(node: ast.expr) -> bool:
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return all(_all_self_eq(v) for v in node.values)
        return (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
            and ast.unparse(node.left) == ast.unparse(node.comparators[0])
        )

    return _all_self_eq(call.args[0])


def ablate(
    harness: str,
    run: Callable[[str], str],
) -> AblationReport:
    """Ablate every top-level assume and report which ones were masking a bug.

    `run` takes a harness source and returns its ESBMC verdict string. Only
    call this on a harness whose unmodified verdict was SUCCESSFUL -- ablation
    of an already-FAILED harness says nothing.
    """
    report = AblationReport(over_restricted=False)
    for variant in build_variants(harness):
        verdict = run(variant.source)
        report.per_assumption[variant.assumption] = verdict
        if verdict == FAILED:
            report.over_restricted = True
            report.masking_assumptions.append(variant.assumption)
    return report
