"""Step 3 helper: extract the precondition allowlist for harness synthesis.

The dominant failure of the LLM synthesizer (smoke test 2026-08-28) is
over-restriction: it invents an `__ESBMC_assume` bound the real caller never
guarantees (`0 <= x <= 1`), ESBMC then verifies the harness SUCCESSFUL, and the
bug disappears. That gap between "safe on the abstraction" and "safe for real"
is the `abstraction_gap`.

This module removes the guessing from one side of it: the only preconditions a
harness is allowed to assume are the ones the real function *itself* enforces,
i.e. the `if <cond>: raise ...` guards and the bare `assert <cond>` statements
at the top of its body. Anything the function does not check is not a
precondition, and the synthesizer is told to add nothing beyond this list.

Pure AST. No LLM, no ESBMC, no network.
"""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass

# Comparison operators and their negations, for turning a rejection guard
# (`if n < 2: raise`) into the precondition it implies (`n >= 2`).
_NEGATED_CMP: dict[type[ast.cmpop], str] = {
    ast.Lt: ">=",
    ast.LtE: ">",
    ast.Gt: "<=",
    ast.GtE: "<",
    ast.Eq: "!=",
    ast.NotEq: "==",
}


@dataclass
class GuardClause:
    """One precondition the real function enforces on its own inputs."""

    precondition: str      # e.g. "n_windows >= 2" -- already in "must hold" form
    origin: str            # "raise" (from `if ...: raise`) or "assert"
    raw: str               # the original guard test, as written in the source


def _raises(stmt: ast.stmt) -> bool:
    """True if this statement is (or its body is only) a `raise`."""
    if isinstance(stmt, ast.Raise):
        return True
    if isinstance(stmt, ast.If):
        return bool(stmt.body) and all(_raises(s) for s in stmt.body)
    return False


def _negate(test: ast.expr) -> str:
    """Return the source of `not test`, simplified for the common shapes."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return ast.unparse(test.operand)
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and type(test.ops[0]) in _NEGATED_CMP
    ):
        left = ast.unparse(test.left)
        right = ast.unparse(test.comparators[0])
        return f"{left} {_NEGATED_CMP[type(test.ops[0])]} {right}"
    return f"not ({ast.unparse(test)})"


def _function_body(source: str) -> list[ast.stmt] | None:
    """Parse a function's source (possibly method-indented) and return its body."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.body
    return None


def extract_guards(source: str) -> list[GuardClause]:
    """Extract the precondition-grade guards from a function's source.

    Only direct children of the function body are considered -- a guard nested
    inside a loop or another `if` is conditional, not a precondition. The scan
    stops at the first statement that is neither a guard, a docstring, nor a
    plain assignment, since anything past real work is post-condition territory.
    """
    body = _function_body(source)
    if body is None:
        return []

    clauses: list[GuardClause] = []
    for stmt in body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring / bare literal
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.Pass)):
            continue  # operand setup, keep scanning
        if isinstance(stmt, ast.If) and stmt.body and all(_raises(s) for s in stmt.body):
            clauses.append(
                GuardClause(
                    precondition=_negate(stmt.test),
                    origin="raise",
                    raw=ast.unparse(stmt.test),
                )
            )
            continue
        if isinstance(stmt, ast.Assert):
            clauses.append(
                GuardClause(
                    precondition=ast.unparse(stmt.test),
                    origin="assert",
                    raw=ast.unparse(stmt.test),
                )
            )
            continue
        break

    # De-duplicate on the precondition text, keep first-seen order.
    seen: dict[str, GuardClause] = {}
    for clause in clauses:
        seen.setdefault(clause.precondition, clause)
    return list(seen.values())


def format_precondition_block(source: str) -> str:
    """Render the guard allowlist for the synthesis prompt.

    Returns a short instruction the user prompt embeds verbatim, so the model
    sees exactly which `__ESBMC_assume` preconditions are legitimate.
    """
    clauses = extract_guards(source)
    if not clauses:
        return (
            "Preconditions the real function enforces on its inputs: NONE.\n"
            "The function validates nothing. Add NO precondition __ESBMC_assume "
            "lines -- only one loose magnitude bound per variable so the search "
            "terminates (e.g. __ESBMC_assume(abs(x) <= 1000))."
        )
    lines = "\n".join(f"  - {c.precondition}   (function does: {c.raw})" for c in clauses)
    return (
        "Preconditions the real function enforces on its inputs -- use EXACTLY "
        "these as __ESBMC_assume, and add NO other precondition:\n"
        f"{lines}\n"
        "Any bound not in this list is over-restriction and hides the bug."
    )
