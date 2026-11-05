"""Smell reports from a static analysis tool, filtered by an LLM that sees the code and the tool's metrics
(iSMELL, Wu et al., ASE 2024). The filter only removes: a report the LLM does not answer keeps the tool's call."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..llm.rate_limit import UsageLimitReached

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "smell_filter.txt"


@dataclass(frozen=True)
class SmellCandidate:
    id: str
    smell: str
    path: str
    line: int
    tool: str
    metrics: dict
    code: str
    first_line: int = 1


def _user_prompt(group: list[SmellCandidate]) -> str:
    reports = [{"id": c.id, "smell": c.smell, "line_in_code": c.line - c.first_line + 1, "tool": c.tool,
                "metrics": c.metrics} for c in group]
    return (f"<UNTRUSTED_PYTHON_CODE>\n{group[0].code}\n</UNTRUSTED_PYTHON_CODE>\n\n"
            f"File: {group[0].path}\n\nReports:\n{json.dumps(reports, indent=1)}\n")


def _answers(raw: str, asked: set[str]) -> dict[str, dict]:
    payload = json.loads(raw)
    verdicts = payload.get("verdicts") if isinstance(payload, dict) else None
    if not isinstance(verdicts, list):
        raise TypeError(f"no verdicts list: {raw[:200]!r}")
    found: dict[str, dict] = {}
    for verdict in verdicts:
        # Only a boolean decides; anything else stays unanswered, so it is counted and asked again.
        if isinstance(verdict, dict) and isinstance(verdict.get("id"), str) and verdict["id"] in asked \
                and verdict["id"] not in found and isinstance(verdict.get("smell"), bool):
            found[verdict["id"]] = {"smell": verdict["smell"], "reason": str(verdict.get("reason", ""))}
    return found


def filter_candidates(candidates: list[SmellCandidate], llm, *, done: dict | None = None,
                      on_answer=None) -> dict[str, dict]:
    """One call per piece of code with all its reports; ``done`` holds earlier answers, which are kept."""
    results: dict[str, dict] = {}
    groups: dict[tuple[str, str], list[SmellCandidate]] = defaultdict(list)
    for candidate in candidates:
        earlier = (done or {}).get(candidate.id)
        if earlier is not None and "error" not in earlier:
            results[candidate.id] = earlier
        elif not candidate.code.strip():
            results[candidate.id] = {"skipped": "no code"}
        else:
            groups[(candidate.path, candidate.code)].append(candidate)
    system = PROMPT.read_text(encoding="utf-8")
    for group in groups.values():
        asked = {c.id for c in group}
        try:
            found = _answers(llm.complete(system, _user_prompt(group), json_mode=True).raw_response, asked)
        except UsageLimitReached:
            raise
        except Exception as exc:  # noqa: BLE001 - each backend raises its own errors; one group must not lose the rest
            found, error = {}, f"{type(exc).__name__}: {exc}"[:300]
        else:
            error = "missing from the answer"
        for candidate in group:
            results[candidate.id] = found.get(candidate.id, {"error": error})
        if on_answer is not None:
            on_answer(results)
    return results


def _block(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if recall == 0.0:
        f1 = 0.0
    elif precision is None or recall is None:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def score(candidates: list[SmellCandidate], labels: dict[str, tuple[str, int]], results: dict[str, dict], *,
          scope: str = "all labelled items") -> dict:
    """Tool alone against tool plus LLM, overall and per smell; ``labels`` covers the labelled items in ``scope``
    (``id -> (smell, 1 or 0)``), so the positives the tool never reported count as misses for both."""
    reported = {c.id for c in candidates}
    kept = {c.id for c in candidates if results.get(c.id, {}).get("smell") is not False}

    def counts(chosen: set[str], smell: str | None) -> dict:
        ids = [i for i, (name, _) in labels.items() if smell is None or name == smell]
        tp = sum(1 for i in ids if i in chosen and labels[i][1] == 1)
        fp = sum(1 for i in ids if i in chosen and labels[i][1] == 0)
        fn = sum(1 for i in ids if i not in chosen and labels[i][1] == 1)
        return _block(tp, fp, fn)

    def unsent(key: str, smell: str | None) -> int:
        return sum(1 for c in candidates if key in results.get(c.id, {}) and (smell is None or c.smell == smell))

    smells = sorted({name for name, _ in labels.values()})
    return {"recall_scope": scope, "tool": counts(reported, None), "tool_llm": counts(kept, None),
            "per_smell": {s: {"tool": counts(reported, s), "tool_llm": counts(kept, s),
                              "llm_errors": unsent("error", s), "no_code": unsent("skipped", s)} for s in smells},
            "llm_errors": unsent("error", None), "no_code": unsent("skipped", None)}


RUFF_SMELLS = {"PLR0913": "LongParameterList", "PLR0915": "LongMethod", "C901": "LongMethod", "PLR0904": "LargeClass"}
_ENCLOSING = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _enclosing(source: str, line: int) -> tuple[str, int]:
    """The innermost function or class that starts at ``line`` or holds it, and its first line."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "", line
    holders = [n for n in ast.walk(tree) if isinstance(n, _ENCLOSING) and n.lineno <= line <= (n.end_lineno or n.lineno)]
    if not holders:
        return "", line
    node = max(holders, key=lambda n: n.lineno)
    first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    return "\n".join(source.splitlines()[first - 1:node.end_lineno]), first


def _ruff() -> str:
    """ruff on the PATH, else the one installed next to this Python (the venv's)."""
    sibling = Path(sys.executable).with_name("ruff")
    return shutil.which("ruff") or (str(sibling) if sibling.exists() else "ruff")


def ruff_candidates(root: Path, ruff: str | None = None) -> list[SmellCandidate]:
    """Size and complexity reports from ruff with its defaults (``--isolated``), named as PySmell's smells.
    Raises RuntimeError when ruff is missing or fails, which is not the same as finding no smell."""
    root = Path(root).resolve()
    try:
        done = subprocess.run([ruff or _ruff(), "check", "--isolated", "--preview", "--select", ",".join(RUFF_SMELLS),
                               "--output-format", "json", str(root)], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"ruff did not run: {exc}") from exc
    # ruff exits 0 with no finding and 1 with findings, printing the JSON list either way.
    if done.returncode not in (0, 1) or not done.stdout.strip():
        raise RuntimeError(f"ruff failed ({done.returncode}): {done.stderr.strip()[:300]}")
    try:
        reports = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ruff printed no JSON: {exc}") from exc
    candidates, sources = [], {}
    for report in reports:
        smell = RUFF_SMELLS.get(report.get("code") or "")
        if smell is None:
            continue
        path = Path(report["filename"])
        line = report["location"]["row"]
        if path not in sources:
            sources[path] = path.read_text(encoding="utf-8", errors="replace")
        code, first = _enclosing(sources[path], line)
        relative = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
        candidates.append(SmellCandidate(f"{relative}:{line}:{report['code']}", smell, relative, line,
                                         f"ruff:{report['code']}", {"message": report.get("message", "")}, code, first))
    return candidates
