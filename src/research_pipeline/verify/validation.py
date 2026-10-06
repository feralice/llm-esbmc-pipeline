"""Whether a verify verdict means what it says: the target is the original code (V1), a "safe"
verdict examined the hypothesis line (V2), and the harness catches faults injected near it (V3)."""

from __future__ import annotations

import ast
from pathlib import Path

from .astutil import body_signature, expression_nodes, find_function
from .render import Program


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
