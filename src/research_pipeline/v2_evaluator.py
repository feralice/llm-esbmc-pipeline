"""Stage-aware evaluation for the V2 real-bug experiment.

The detector and synthesizer never read these artifacts. Evaluation happens
after the run, using the manifest only to map neutral detection sources to the
known labels. This prevents oracle leakage into either LLM prompt.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .scan.pipeline import (
    FAILURE_GROUNDING,
    FAILURE_SYNTHESIS,
    FAILURE_UNATTRIBUTED,
    FAILURE_VERIFICATION,
)


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def _signature(file: str, category: str) -> tuple[str, str]:
    return str(Path(file).resolve()), category


def _failure_stage(result) -> str:
    """Read the explicit stage, with a compatibility fallback for old reports."""
    stage = str(getattr(result, "failure_stage", "") or "")
    if stage:
        return stage
    classification = str(getattr(result, "classification", ""))
    if classification == "confirmed_unverified":
        return FAILURE_GROUNDING
    if classification in {"invalid_harness", "unsupported_harness", "no_property", "synth_failed"}:
        return FAILURE_SYNTHESIS
    if classification in {
        "safe_native", "safe_driver", "safe_on_abstraction", "over_restricted",
        "esbmc_inconclusive", "esbmc_unavailable",
    }:
        return FAILURE_VERIFICATION
    return FAILURE_UNATTRIBUTED


def evaluate_v2_results(
    *,
    candidates: list,
    results: list,
    ground_truth_path: str | Path,
    manifest_path: str | Path | None = None,
    evaluated_sources: list[str | Path] | None = None,
    rejected_findings: list[dict] | None = None,
    evaluate_detection: bool = True,
) -> dict:
    """Return detection, synthesis-conditional and end-to-end V2 metrics."""
    gt_path = Path(ground_truth_path)
    manifest_file = Path(manifest_path) if manifest_path else gt_path.parent / "manifest.json"
    gt_items = json.loads(gt_path.read_text(encoding="utf-8")).get("items", [])
    manifest_items = json.loads(manifest_file.read_text(encoding="utf-8")).get("items", [])
    gt_ids = {str(item.get("id")) for item in gt_items}
    manifest_ids = {str(item.get("id")) for item in manifest_items}
    if gt_ids != manifest_ids:
        raise ValueError("ground truth and V2 manifest contain different case IDs")

    base = manifest_file.parent
    allowed_sources = (
        {str(Path(path).resolve()) for path in evaluated_sources}
        if evaluated_sources is not None
        else None
    )
    expected = Counter(
        _signature(str(base / item["detection_file"]), str(category))
        for item in manifest_items
        for category in item.get("categories", [])
        if allowed_sources is None
        or str((base / item["detection_file"]).resolve()) in allowed_sources
    )
    generated = Counter(_signature(c.file, c.category) for c in candidates)
    generated.update(
        _signature(str(item["file"]), str(item["category"]))
        for item in (rejected_findings or [])
    )
    matched = expected & generated
    detection_tp = sum(matched.values())
    detection_fp = sum((generated - expected).values())
    detection_fn = sum((expected - generated).values())

    result_by_signature: dict[tuple[str, str], list] = {}
    for result in results:
        sig = _signature(result.candidate.file, result.candidate.category)
        result_by_signature.setdefault(sig, []).append(result)

    true_positive_results = []
    remaining = matched.copy()
    false_hypothesis_results = []
    for sig, grouped in result_by_signature.items():
        allowed = remaining.get(sig, 0)
        true_positive_results.extend(grouped[:allowed])
        false_hypothesis_results.extend(grouped[allowed:])
        remaining[sig] = max(0, allowed - len(grouped))

    # A detection true positive can be present only in rejected_findings when
    # the AST/expression grounding filter discarded it before synthesis. Match
    # those occurrences against the still-unprocessed true positives so the
    # stage accounting is disjoint and sums to detection_tp - end_to_end_tp.
    rejected_signatures = Counter(
        _signature(str(item["file"]), str(item["category"]))
        for item in (rejected_findings or [])
    )
    grounding_unprocessed = sum(
        min(count, rejected_signatures.get(sig, 0))
        for sig, count in remaining.items()
    )
    other_unprocessed = sum(remaining.values()) - grounding_unprocessed

    compatible = sum(
        r.compat_verdict in {"ok", "skipped", "native_function", "driver"}
        for r in true_positive_results
    )
    confirmed_native = sum(r.classification == "confirmed_native" for r in true_positive_results)
    confirmed_driver = sum(r.classification == "confirmed_driver" for r in true_positive_results)
    confirmed = confirmed_native + confirmed_driver + sum(
        r.classification == "confirmed_on_abstraction" for r in true_positive_results
    )
    unverified = sum(r.classification == "confirmed_unverified" for r in true_positive_results)
    over_restricted = sum(r.classification == "over_restricted" for r in true_positive_results)
    repaired = sum(
        r.classification == "confirmed_on_abstraction" and r.attempts > 1
        for r in true_positive_results
    )

    end_to_end_tp = confirmed
    end_to_end_fp = sum(
        r.classification in {"confirmed_on_abstraction", "confirmed_native", "confirmed_driver"}
        for r in false_hypothesis_results
    )
    end_to_end_fn = sum(expected.values()) - end_to_end_tp
    stage_losses = Counter()
    for result in true_positive_results:
        if result.classification not in {
            "confirmed_native", "confirmed_driver", "confirmed_on_abstraction"
        }:
            stage_losses[_failure_stage(result)] += 1
    if grounding_unprocessed:
        stage_losses[FAILURE_GROUNDING] += grounding_unprocessed
    if other_unprocessed:
        stage_losses[FAILURE_UNATTRIBUTED] += other_unprocessed
    stage_loss_total = sum(stage_losses.values())
    detection_metrics = {
        "tp": detection_tp, "fp": detection_fp, "fn": detection_fn,
        **_prf(detection_tp, detection_fp, detection_fn),
    } if evaluate_detection else {"status": "not_evaluated_oracle_seeded"}
    end_to_end_metrics = {
        "tp": end_to_end_tp, "fp": end_to_end_fp, "fn": end_to_end_fn,
        **_prf(end_to_end_tp, end_to_end_fp, end_to_end_fn),
    } if evaluate_detection else {"status": "not_evaluated_oracle_seeded"}
    return {
        "unit": "category label on a detection source",
        "expected_labels": sum(expected.values()),
        "detection": detection_metrics,
        "synthesis_given_correct_detection": {
            "n": len(true_positive_results),
            "compatible": compatible,
            "compatibility_rate": compatible / len(true_positive_results) if true_positive_results else None,
            "confirmed_on_abstraction": confirmed,
            "confirmation_rate": confirmed / len(true_positive_results) if true_positive_results else None,
            "confirmed_native": confirmed_native,
            "confirmed_driver": confirmed_driver,
            "repaired_then_confirmed": repaired,
            "over_restricted": over_restricted,
            "unverified": unverified,
        },
        "pipeline_stage_losses": {
            "correct_detection_labels": detection_tp,
            "confirmed_end_to_end": end_to_end_tp,
            "total_losses": stage_loss_total,
            "by_stage": dict(sorted(stage_losses.items())),
        },
        "end_to_end": end_to_end_metrics,
    }
