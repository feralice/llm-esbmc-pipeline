"""Smell reports from a static analysis tool, filtered by an LLM that sees the code and the tool's metrics
(iSMELL, Wu et al., ASE 2024). The filter only removes: a report the LLM does not answer keeps the tool's call."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

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
        if isinstance(verdict, dict) and verdict.get("id") in asked and verdict["id"] not in found:
            found[verdict["id"]] = {"smell": verdict.get("smell"), "reason": str(verdict.get("reason", ""))}
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
    if precision is None or recall is None:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def score(candidates: list[SmellCandidate], labels: dict[str, tuple[str, int]], results: dict[str, dict]) -> dict:
    """Tool alone against tool plus LLM, overall and per smell; ``labels`` covers every labelled item
    (``id -> (smell, 1 or 0)``), so the positives the tool never reported count as misses for both."""
    reported = {c.id for c in candidates}
    kept = {c.id for c in candidates if results.get(c.id, {}).get("smell") is not False}

    def counts(chosen: set[str], smell: str | None) -> dict:
        ids = [i for i, (name, _) in labels.items() if smell is None or name == smell]
        tp = sum(1 for i in ids if i in chosen and labels[i][1] == 1)
        fp = sum(1 for i in ids if i in chosen and labels[i][1] == 0)
        fn = sum(1 for i in ids if i not in chosen and labels[i][1] == 1)
        return _block(tp, fp, fn)

    smells = sorted({name for name, _ in labels.values()})
    return {"tool": counts(reported, None), "tool_llm": counts(kept, None),
            "per_smell": {s: {"tool": counts(reported, s), "tool_llm": counts(kept, s)} for s in smells},
            "llm_errors": sum(1 for c in candidates if "error" in results.get(c.id, {})),
            "no_code": sum(1 for c in candidates if "skipped" in results.get(c.id, {}))}
