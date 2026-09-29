"""Assign a suspect expression and a heuristic category to each staged candidate, without an LLM.

The LLM is what the dataset evaluates, so it must not write the labels. The suspect expression
comes from the fix itself (buggy vs fixed file); the category from fixed patterns in the code the
fix adds, marked as heuristic and pending human review. Writes dataset/v2_candidates/labels.json.
"""

from __future__ import annotations

import ast
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.scan.rewrite_guard import _expression_nodes, _find_function  # noqa: E402

STAGING = ROOT / "dataset" / "v2_candidates"
# First match wins: the most specific evidence first.
_CATEGORY_RULES = (
    ("none_misuse", re.compile(r"\bis (not )?None\b|[!=]= None\b")),
    ("division_by_zero", re.compile(r"ZeroDivisionError|[!=]= 0(\.0)?\b|\b0(\.0)? [!=]=")),
    ("out_of_bounds", re.compile(r"IndexError|KeyError|\blen\(")),
    ("type_mismatch", re.compile(r"\bisinstance\(|TypeError")),
    ("integer_overflow", re.compile(r"OverflowError")),
    ("invalid_precondition", re.compile(r"\braise ValueError\b|\bassert\b")),
)


def category_from_fix(added_lines: list[str]) -> str:
    text = "\n".join(added_lines)
    return next((name for name, rule in _CATEGORY_RULES if rule.search(text)), "unclassified")


def _statement_at(function: ast.FunctionDef, line: int) -> ast.stmt | None:
    """Innermost statement of the function that starts on ``line``, or spans it."""
    found = [node for node in ast.walk(function) if isinstance(node, ast.stmt) and node is not function
             and node.lineno <= line <= (node.end_lineno or node.lineno)]
    # A nested def or class only frames the change; the statement inside it is the suspect.
    found = [n for n in found if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))] or found
    starting = [node for node in found if node.lineno == line]
    pool = starting or found
    return min(pool, key=lambda n: (n.end_lineno or n.lineno) - n.lineno) if pool else None


def _is_docstring(statement: ast.stmt) -> bool:
    return (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str))


def _suspect(source: str, statement: ast.stmt) -> str:
    # For a compound statement only its header matters: the condition or the iterable.
    head = getattr(statement, "test", None) if isinstance(statement, (ast.If, ast.While, ast.Assert)) else None
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        head = statement.iter
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        head = statement.items[0].context_expr
    return (ast.get_source_segment(source, head or statement) or "").strip()


def label_pair(buggy: str, fixed: str, function_name: str) -> dict:
    result = {"expression": "", "expression_source": "", "category": "unclassified",
              "category_source": "heuristic_from_fix_diff", "grounded": False}
    try:
        function = _find_function(ast.parse(buggy), function_name)
    except SyntaxError:
        function = None
    if function is None:
        result["expression_source"] = "function_not_found"
        return result
    start, end = function.lineno, function.end_lineno
    buggy_lines, fixed_lines = buggy.splitlines(), fixed.splitlines()
    changed, inserted_after, added = [], [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, buggy_lines, fixed_lines, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        added += fixed_lines[j1:j2]
        if tag in {"replace", "delete"}:
            changed += [line for line in range(i1 + 1, i2 + 1) if start <= line <= end and buggy_lines[line - 1].strip()]
        elif start <= i1 + 1 <= end:
            inserted_after.append(i1 + 1)
    result["category"] = category_from_fix(added)
    lines, source_kind = (changed, "changed_line") if changed else (inserted_after, "statement_after_insertion")
    for line in lines:
        statement = _statement_at(function, line)
        if statement is None or _is_docstring(statement):
            continue
        expression = _suspect(buggy, statement)
        if expression:
            result.update(expression=expression, expression_source=source_kind, line=line,
                          grounded=bool(_expression_nodes(function, expression)))
            return result
    result["expression_source"] = "no_statement_at_change"
    return result


def main() -> int:
    candidates = json.loads((STAGING / "bugsinpy_candidates.json").read_text(encoding="utf-8"))
    labels = []
    for candidate in candidates:
        sources = STAGING / "sources"
        buggy = (sources / f"{candidate['id']}.buggy.py").read_text(encoding="utf-8", errors="replace")
        fixed_path = sources / f"{candidate['id']}.fixed.py"
        fixed = fixed_path.read_text(encoding="utf-8", errors="replace") if fixed_path.exists() else buggy
        labels.append({"id": candidate["id"], "function": candidate["function"],
                       **label_pair(buggy, fixed, candidate["function"]), "review": "pending"})
    (STAGING / "labels.json").write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    print("expressão:", dict(Counter(l["expression_source"] for l in labels)))
    print("aterrada:", sum(l["grounded"] for l in labels), "de", len(labels))
    print("categoria:", dict(Counter(l["category"] for l in labels).most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
