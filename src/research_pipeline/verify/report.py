"""Aggregate V2 verify-engine verdicts and score them against the V2 ground truth by location."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from research_pipeline.v2_evaluator import (
    _bug_detection_metrics,
    at_bug_line,
    evaluate_detection,
)

from .outcome import CHECKED, CONFIRMED, OTHER_FAILURE, PIPELINE_ERROR, VALUE_CONFIRMED, VERDICTS

MAX_CALLS = 3


def failed_in_function(result: dict) -> bool:
    """An OTHER_FAILURE whose replay raised inside the hypothesis's function, at a line other than its own."""
    replay = result.get("replay") or {}
    line, span = replay.get("line"), replay.get("target_range")
    return (result["verdict"] == OTHER_FAILURE and isinstance(line, int) and bool(span) and bool(span[1])
            and span[0] <= line <= span[1])


def _operational_failures(results: list[dict]) -> dict:
    """Cases the pipeline could not process (network, quota, crash): no verdict about the hypothesis, so apart."""
    reasons = Counter(str(r.get("reason", "")).split(":")[0] or "unknown"
                      for r in results if r["verdict"] == PIPELINE_ERROR)
    return {"count": sum(reasons.values()), "by_reason": dict(reasons)}


def summarize(results: list[dict]) -> dict:
    """success@k: share of hypotheses that reached the LLM and got a checked verdict within k calls."""
    counts = Counter(r["verdict"] for r in results)
    reached = [r for r in results if r.get("llm_calls", 0) > 0]
    success = {
        str(k): (sum(r["verdict"] in CHECKED and r["llm_calls"] <= k for r in reached) / len(reached)
                 if reached else None)
        for k in range(1, MAX_CALLS + 1)
    }
    return {
        "n": len(results),
        # The engine's verdicts always listed; any other (the agent's) only when it occurs.
        "by_verdict": {**{verdict: counts.get(verdict, 0) for verdict in VERDICTS},
                       **{verdict: n for verdict, n in counts.items() if verdict not in VERDICTS}},
        # Inside by_verdict's OTHER_FAILURE, never added to CONFIRMED.
        "same_function_other_line": sum(failed_in_function(r) for r in results),
        "operational_failures": _operational_failures(results),
        "reached_llm": len(reached),
        "success_at_k": success,
    }


def _expected_items(ground_truth_path: Path, evaluated_sources: list) -> tuple[list[dict], Path]:
    manifest_file = Path(ground_truth_path).parent / "manifest.json"
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    base = manifest_file.parent
    excluded = {str(i) for i in payload.get("evaluation_policy", {}).get("patch_context_items", [])}
    allowed = {str(Path(p).resolve()) for p in evaluated_sources}
    items = [item for item in payload.get("items", [])
             if str(item.get("id")) not in excluded
             and str((base / item["detection_file"]).resolve()) in allowed]
    return items, base


def _confirmed_by_location(results: list[dict], verdict: str, items: list[dict], base: Path) -> dict:
    found = [
        {"file": r["hypothesis"]["file"], "function": r["hypothesis"]["function"],
         "expression": r["hypothesis"]["suspect_expression"]}
        for r in results if r["verdict"] == verdict
    ]
    metrics = _bug_detection_metrics(items, found, base)
    metrics.pop("triage")  # every confirmed hypothesis was sent; triage says nothing here
    return metrics


def _bugs_hit(results: list[dict], items: list[dict], base: Path, *, at_line: bool) -> set[str]:
    def hits(item: dict, hypothesis: dict) -> bool:
        if str(Path(hypothesis["file"]).resolve()) != str((base / item["detection_file"]).resolve()):
            return False
        if at_line:
            return at_bug_line(hypothesis, item)
        return hypothesis["function"] in {f.strip() for f in str(item.get("function", "")).split("/")}

    return {str(item["id"]) for item in items if item.get("categories")
            and any(hits(item, r["hypothesis"]) for r in results)}


def _same_function_other_line(results: list[dict], items: list[dict], base: Path) -> dict:
    """Labelled bugs whose function failed under ESBMC and the replay at another line than the hypothesis."""
    other = [r for r in results if failed_in_function(r)]
    bugs = _bugs_hit(other, items, base, at_line=False)
    confirmed = _bugs_hit([r for r in results if r["verdict"] == CONFIRMED], items, base, at_line=True)
    return {"hypotheses": len(other), "bugs": len(bugs), "bugs_not_confirmed_at_line": len(bugs - confirmed),
            "bug_ids": sorted(bugs)}


def evaluate_verify(results: list[dict], candidates: list, ground_truth_path: str | Path,
                evaluated_sources: list, rejected_findings: list[dict]) -> dict:
    detection = evaluate_detection(candidates=candidates, ground_truth_path=ground_truth_path,
                                   evaluated_sources=evaluated_sources, rejected_findings=rejected_findings)
    items, base = _expected_items(Path(ground_truth_path), evaluated_sources)
    return {
        "triage": detection["triage"],
        "detection_by_location": detection["bug_detection"],
        "confirmed_by_location": _confirmed_by_location(results, CONFIRMED, items, base),
        # Kept apart: a wrong-result confirmation rests on an LLM-written property and the fixed-version control.
        "value_confirmed_by_location": _confirmed_by_location(results, VALUE_CONFIRMED, items, base),
        # A separate bucket: the main metric stays confirmed_by_location.
        "same_function_other_line": _same_function_other_line(results, items, base),
    }
