"""Restore original source for replay, independently of the agent orchestrator."""

from __future__ import annotations

import ast
import re
import textwrap

from .astutil import expression_nodes
from .render import Program
from .replay import ReplayVerdict, concrete_replay

def without_esbmc_imports(source: str) -> str:
    """CPython has no ``esbmc`` module; the replay worker provides those names instead."""
    return re.sub(r"^(from esbmc import .*|import esbmc.*)$", "", source, flags=re.MULTILINE)

def first_line(node: ast.FunctionDef) -> int:
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])

def replay_original(harness: str, target: ast.FunctionDef, original: str, original_target: ast.FunctionDef | None,
                     expression: str | None, seeds: dict[str, list], inputs: list | None = None,
                     random_seed: int | None = None, *, replay=concrete_replay) -> tuple[ReplayVerdict, ast.Module | None]:
    """Replay the agent's harness with its simplified target swapped back for the original function;
    also returns the replayed program's tree. Without ``expression`` the whole function is the span;
    ``random_seed`` makes it one random run instead of ESBMC's values."""
    if original_target is None:
        return ReplayVerdict("unavailable", reason="original function not found"), None
    first = first_line(target)
    source = "\n".join(original.splitlines()[first_line(original_target) - 1:original_target.end_lineno])
    body = textwrap.indent(textwrap.dedent(source), " " * target.col_offset).splitlines()
    lines = harness.splitlines()
    spliced = "\n".join([*lines[:first - 1], *body, *lines[target.end_lineno:]]) + "\n"
    def_line = first + original_target.lineno - first_line(original_target)
    try:
        tree = ast.parse(spliced)
    except SyntaxError as exc:
        return ReplayVerdict("unavailable", reason=f"original body does not fit the harness: {exc.msg}"), None
    swapped = next((n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.lineno == def_line), None)
    if swapped is None:
        return ReplayVerdict("unavailable", reason="original function does not fit the harness"), None
    raw_nodes = expression_nodes(swapped, expression) if expression is not None else [swapped]
    nodes = [node for node in raw_nodes if isinstance(node, (ast.expr, ast.stmt))]
    if not nodes:
        return ReplayVerdict("unavailable", reason="suspect expression missing from the original function"), None
    program = Program(without_esbmc_imports(spliced), 0,
                      tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes})), (),
                      (swapped.lineno, swapped.end_lineno or swapped.lineno))
    if inputs is not None:
        return replay(program, swapped.name, inputs=inputs), tree
    if random_seed is not None:
        return replay(program, swapped.name, max_runs=0, random_runs=1, seed=random_seed), tree
    return replay(program, swapped.name, seeds=seeds, seeds_only=True), tree
