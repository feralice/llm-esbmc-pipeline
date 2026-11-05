"""Cap the hypotheses one function sends to ESBMC (the rule of the offline analysis of 03/11)."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.hypothesis import undo_prompt_rename


def _syntax_key(candidate: Candidate) -> tuple[str, str, str, str]:
    expression = undo_prompt_rename(candidate.expression, candidate.function)
    try:
        syntax = ast.dump(ast.parse(expression), include_attributes=False)
    except SyntaxError:
        syntax = " ".join(expression.split())
    return str(Path(candidate.file).resolve()), candidate.function, syntax, candidate.oracle


def cap_per_function(candidates: list[Candidate], limit: int) -> tuple[list[Candidate], list[Candidate]]:
    """Keep, per file and function, the first ``limit`` syntactically distinct expressions in the order the
    LLM wrote them; a repeat of a kept expression (same oracle) is dropped too. Returns (kept, dropped)."""
    seen: set[tuple[str, str, str, str]] = set()
    per_function: dict[tuple[str, str], int] = defaultdict(int)
    kept: list[Candidate] = []
    dropped: list[Candidate] = []
    for candidate in candidates:
        key = _syntax_key(candidate)
        if key in seen or per_function[key[:2]] >= limit:
            dropped.append(candidate)
            continue
        seen.add(key)
        per_function[key[:2]] += 1
        kept.append(candidate)
    return kept, dropped
