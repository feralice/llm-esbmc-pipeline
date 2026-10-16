"""Aggregate V2 verify-engine verdicts and score them against the V2 ground truth by location."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from research_pipeline.v2_evaluator import _bug_detection_metrics, evaluate_detection

from .outcome import CHECKED, CONFIRMED, VALUE_CONFIRMED, VERDICTS

MAX_CALLS = 3


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
        "by_verdict": {verdict: counts.get(verdict, 0) for verdict in VERDICTS},
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
    }
