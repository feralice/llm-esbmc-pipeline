"""Whether a verify verdict means what it says: the target is the original code (V1), a "safe"
verdict examined the hypothesis line (V2), and the harness catches faults injected near it (V3)."""

from __future__ import annotations

import ast
from pathlib import Path

from .astutil import body_signature, expression_nodes, find_function
from .outcome import CONFIRMED
from .procs import run_group
from .render import Program

REACHABLE, UNREACHABLE, INCONCLUSIVE = "reachable", "unreachable", "inconclusive"
_REACH = "reachability: unreachable code reached"


def program_for_result(path: Path, hypothesis: dict) -> Program | None:
    source = path.read_text(encoding="utf-8")
    function = find_function(ast.parse(source), hypothesis["function"])
    if function is None:
        return None
    nodes = expression_nodes(function, hypothesis["suspect_expression"])
    if not nodes:
        return None
    spans = tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes}))
    return Program(source, 0, spans, (), (function.lineno, function.end_lineno))


def target_preserved(original_source: str, program_source: str, function: str) -> bool:
    original = find_function(ast.parse(original_source), function)
    checked = find_function(ast.parse(program_source), function)
    return original is not None and checked is not None and body_signature(original) == body_signature(checked)


def with_unreachable_marker(source: str, line: int) -> str | None:
    """The program with ``__ESBMC_unreachable()`` right before the statement holding ``line``."""
    covering = [n for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.stmt) and n.lineno <= line <= (n.end_lineno or n.lineno)]
    if not covering:
        return None
    statement = max(covering, key=lambda n: (n.lineno, n.col_offset))
    lines = source.splitlines()
    lines.insert(statement.lineno - 1, " " * statement.col_offset + "__ESBMC_unreachable()")
    marked = "\n".join(lines) + "\n"
    try:
        ast.parse(marked)
    except SyntaxError:
        return None  # e.g. an elif condition: nothing can go between the branches
    return marked


def read_reachability(output: str | None) -> str:
    if output is None:
        return INCONCLUSIVE
    lines = output.splitlines()
    if any("FAILED" in line and _REACH in line for line in lines):
        return REACHABLE
    if any("FAILED" in line and "unwinding assertion" in line for line in lines):
        return INCONCLUSIVE  # a truncated loop proves nothing about reachability
    if any("PASSED" in line and _REACH in line for line in lines) or "VERIFICATION SUCCESSFUL" in output:
        return UNREACHABLE
    return INCONCLUSIVE


def reachability(program: Program, *, esbmc: str, unwind: int, timeout_seconds: int, work_dir: Path) -> str:
    if not program.target_spans:
        return INCONCLUSIVE
    marked = with_unreachable_marker(program.source, program.target_spans[0][0])
    if marked is None:
        return INCONCLUSIVE
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "reach.py"
    path.write_text(marked, encoding="utf-8")
    done = run_group([esbmc, path.name, "--enable-unreachability-intrinsic", "--unwind", str(unwind),
                      "--multi-property"], timeout_seconds=timeout_seconds, cwd=work_dir)
    return read_reachability(None if done is None else done.stdout + done.stderr)


def natural_mutation_matrix(buggy: list[dict], fixed: list[dict]) -> dict:
    """Confirmed on the buggy version only: the bug. On both: a crash the fix did not touch (a false
    alarm for the reported bug, e.g. an input no caller passes)."""
    fixed_confirmed = {r["hypothesis"]["hypothesis_id"] for r in fixed if r["verdict"] == CONFIRMED}
    matrix: dict = {"only_buggy": [], "both": [], "only_fixed": [], "neither": 0}
    for result in buggy:
        hid = result["hypothesis"]["hypothesis_id"]
        on_buggy, on_fixed = result["verdict"] == CONFIRMED, hid in fixed_confirmed
        if on_buggy and on_fixed:
            matrix["both"].append(hid)
        elif on_buggy:
            matrix["only_buggy"].append(hid)
        elif on_fixed:
            matrix["only_fixed"].append(hid)
        else:
            matrix["neither"] += 1
    return matrix
