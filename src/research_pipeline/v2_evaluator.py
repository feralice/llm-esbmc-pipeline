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


def _accepted_answers(item: dict) -> list[str]:
    """Every label that counts as the right answer for a manifest item."""
    return [*map(str, item.get("categories", [])), *map(str, item.get("harness_strategies", []))]


def _expected_slots(item: dict) -> list[frozenset[str]]:
    """One expected label per slot.

    An item with ``harness_strategies`` is one slot answered by any listed
    strategy (the V2 detector's four-value output). Legacy items keep one
    slot per semantic category.
    """
    strategies = item.get("harness_strategies")
    if strategies:
        return [frozenset(map(str, strategies))]
    return [frozenset({str(category)}) for category in item.get("categories", [])]


def _slot_key(slot: frozenset[str]) -> str:
    return "|".join(sorted(slot))


def _bug_detection_metrics(
    expected_items: list[dict], candidates: list, base: Path,
    rejected_findings: list[dict] | None = None,
) -> dict:
    """Measure case localization independently from category classification."""
    expected = [
        {
            "file": str((base / item["detection_file"]).resolve()),
            # "gamma / lgamma": the same bug appears in each listed function.
            "functions": {part.strip() for part in str(item.get("function", "")).split("/") if part.strip()},
            "expression": str(item.get("expression", "")),
            "categories": set(_accepted_answers(item)),
        }
        for item in expected_items
        if item.get("categories")
    ]
    generated = [
        {
            "file": str(Path(candidate["file"]).resolve())
            if isinstance(candidate, dict)
            else str(Path(candidate.file).resolve()),
            "function": str(candidate.get("function", ""))
            if isinstance(candidate, dict)
            else str(candidate.function),
            "expression": str(candidate.get("expression", ""))
            if isinstance(candidate, dict)
            else str(candidate.expression),
            "category": str(candidate.get("category", ""))
            if isinstance(candidate, dict)
            else str(candidate.category),
        }
        for candidate in [*candidates, *(rejected_findings or [])]
    ]

    def count_matches(predicate) -> dict[str, float | None | int]:
        matched = sum(
            any(predicate(item, candidate) for candidate in generated)
            for item in expected
        )
        false_positives = sum(
            not any(predicate(item, candidate) for item in expected)
            for candidate in generated
        )
        false_negatives = len(expected) - matched
        return {
            "tp": matched,
            "fp": false_positives,
            "fn": false_negatives,
            **_prf(matched, false_positives, false_negatives),
        }

    def matches_primary_location(item: dict, candidate: dict) -> bool:
        """Match the strongest location fields available in the manifest."""
        if candidate["file"] != item["file"]:
            return False
        if item["functions"] and candidate["function"] not in item["functions"]:
            return False
        if item["expression"] and candidate["expression"] != item["expression"]:
            return False
        return True

    file_metrics = count_matches(lambda item, candidate: candidate["file"] == item["file"])
    location_metrics = count_matches(
        lambda item, candidate: (
            candidate["file"] == item["file"]
            and candidate["function"] in item["functions"]
        )
    )
    expression_metrics = count_matches(
        lambda item, candidate: (
            candidate["file"] == item["file"]
            and candidate["function"] in item["functions"]
            and candidate["expression"] == item["expression"]
        )
    )
    detection_metrics = count_matches(matches_primary_location)
    category_given_location = {
        "tp": sum(
            any(
                candidate["file"] == item["file"]
                and candidate["function"] in item["functions"]
                and candidate["category"] in item["categories"]
                for candidate in generated
            )
            for item in expected
        ),
    }
    category_given_location["fp"] = 0
    category_given_location["fn"] = len(expected) - category_given_location["tp"]
    category_given_location.update(
        _prf(
            category_given_location["tp"],
            category_given_location["fp"],
            category_given_location["fn"],
        )
    )
    return {
        "detection": detection_metrics,
        "file": file_metrics,
        "location": location_metrics,
        "expression": expression_metrics,
        "category_given_location": category_given_location,
    }


_CONFIRMATION_CLASSIFICATIONS = frozenset(
    {"confirmed_native", "confirmed_driver", "confirmed_on_abstraction"}
)
_REAL_BODY_TIERS = frozenset({"native", "real_body", "driver"})


def is_real_body_confirmation(result) -> bool:
    """Return whether the result is a confirmation backed by real code.

    ``confirmed_original`` counts because its ESBMC witness was replayed on the
    original code and raised the same exception at the suspect operation;
    ``rewrite_violation_empirical`` never does.
    """
    tier = getattr(result, "harness_tier", "")
    return (
        (result.classification in {"confirmed_native", "confirmed_driver"} and tier in _REAL_BODY_TIERS)
        or (result.classification == "confirmed_original" and tier == "rewrite")
    )


def is_scalar_abstraction_confirmation(result) -> bool:
    """Return whether ESBMC confirmed only the scalar abstraction."""
    return (
        result.classification == "confirmed_on_abstraction"
        and getattr(result, "harness_tier", "") == "scalar"
    )


def _is_unknown_confirmation(result) -> bool:
    return (
        result.classification in _CONFIRMATION_CLASSIFICATIONS
        and not is_real_body_confirmation(result)
        and not is_scalar_abstraction_confirmation(result)
    )


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
    manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_items = manifest_payload.get("items", [])
    patch_context_ids = {
        str(item)
        for item in manifest_payload.get("evaluation_policy", {}).get(
            "patch_context_items", []
        )
    }
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
    slots_by_file: dict[str, list[frozenset[str]]] = {}
    for item in manifest_items:
        source = str((base / item["detection_file"]).resolve())
        if str(item.get("id")) in patch_context_ids:
            continue
        if allowed_sources is not None and source not in allowed_sources:
            continue
        slots_by_file.setdefault(source, []).extend(_expected_slots(item))
    expected = Counter(
        (source, _slot_key(slot)) for source, slots in slots_by_file.items() for slot in slots
    )

    def answer_signature(file: str, category: str) -> tuple[str, str]:
        """Map an answer onto the expected slot it satisfies, if any."""
        source, category = _signature(file, category)
        slot = next((s for s in slots_by_file.get(source, []) if category in s), None)
        return (source, _slot_key(slot)) if slot else (source, category)

    generated = Counter(answer_signature(c.file, c.category) for c in candidates)
    generated.update(
        answer_signature(str(item["file"]), str(item["category"]))
        for item in (rejected_findings or [])
    )
    matched = expected & generated
    detection_tp = sum(matched.values())
    detection_fp = sum((generated - expected).values())
    detection_fn = sum((expected - generated).values())

    location_detection = _bug_detection_metrics(
        [
            item
            for item in manifest_items
            if str(item.get("id")) not in patch_context_ids
            and (
                allowed_sources is None
                or str((base / item["detection_file"]).resolve()) in allowed_sources
            )
        ],
        candidates,
        base,
        rejected_findings,
    )

    result_by_signature: dict[tuple[str, str], list] = {}
    for result in results:
        sig = answer_signature(result.candidate.file, result.candidate.category)
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
        answer_signature(str(item["file"]), str(item["category"]))
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
    confirmed_original = sum(r.classification == "confirmed_original" for r in true_positive_results)
    rewrite_violation_empirical = sum(
        r.classification == "rewrite_violation_empirical" for r in true_positive_results
    )
    rewrite_status = Counter(
        r.rewrite_status for r in true_positive_results if getattr(r, "rewrite_status", "")
    )
    confirmed_on_real_body = sum(is_real_body_confirmation(r) for r in true_positive_results)
    confirmed_on_abstraction = sum(
        is_scalar_abstraction_confirmation(r) for r in true_positive_results
    )
    unknown_evidence = sum(_is_unknown_confirmation(r) for r in true_positive_results)
    unverified = sum(r.classification == "confirmed_unverified" for r in true_positive_results)
    category_evidence = Counter(
        getattr(r, "category_evidence", "") or "unrecorded"
        for r in true_positive_results
        if is_real_body_confirmation(r) or is_scalar_abstraction_confirmation(r)
    )
    over_restricted = sum(r.classification == "over_restricted" for r in true_positive_results)
    repaired = sum(
        is_scalar_abstraction_confirmation(r) and r.attempts > 1
        for r in true_positive_results
    )

    end_to_end_tp = confirmed_on_real_body
    end_to_end_fp = sum(
        is_real_body_confirmation(r)
        for r in false_hypothesis_results
    )
    end_to_end_fn = sum(expected.values()) - end_to_end_tp
    stage_losses = Counter()
    for result in true_positive_results:
        if is_scalar_abstraction_confirmation(result):
            stage_losses["abstraction_only"] += 1
        elif result.classification == "rewrite_violation_empirical":
            stage_losses["rewrite_only"] += 1
        elif _is_unknown_confirmation(result):
            stage_losses["unknown_evidence"] += 1
        elif not is_real_body_confirmation(result):
            stage_losses[_failure_stage(result)] += 1
    if grounding_unprocessed:
        stage_losses[FAILURE_GROUNDING] += grounding_unprocessed
    if other_unprocessed:
        stage_losses[FAILURE_UNATTRIBUTED] += other_unprocessed
    stage_loss_total = sum(stage_losses.values())
    detection_metrics = (
        location_detection["detection"]
        if evaluate_detection
        else {"status": "not_evaluated_oracle_seeded"}
    )
    end_to_end_metrics = {
        "tp": end_to_end_tp, "fp": end_to_end_fp, "fn": end_to_end_fn,
        **_prf(end_to_end_tp, end_to_end_fp, end_to_end_fn),
    } if evaluate_detection else {"status": "not_evaluated_oracle_seeded"}
    return {
        "unit": "category label on a detection source",
        "detection_scope": "items without patch context",
        "excluded_patch_context_items": len(patch_context_ids),
        "expected_labels": sum(expected.values()),
        "detection": detection_metrics,
        "bug_detection": location_detection,
        "synthesis_given_correct_detection": {
            "n": len(true_positive_results),
            "compatible": compatible,
            "compatibility_rate": compatible / len(true_positive_results) if true_positive_results else None,
            "confirmed_on_real_body": confirmed_on_real_body,
            "confirmed_on_abstraction": confirmed_on_abstraction,
            "unknown_evidence": unknown_evidence,
            "confirmation_rate": confirmed_on_real_body / len(true_positive_results) if true_positive_results else None,
            "abstraction_only_rate": confirmed_on_abstraction / len(true_positive_results) if true_positive_results else None,
            "confirmed_native": confirmed_native,
            "confirmed_driver": confirmed_driver,
            "confirmed_original": confirmed_original,
            "rewrite_violation_empirical": rewrite_violation_empirical,
            "rewrite_status": dict(sorted(rewrite_status.items())),
            "repaired_then_confirmed": repaired,
            "over_restricted": over_restricted,
            "unverified": unverified,
            "category_evidence": dict(sorted(category_evidence.items())),
        },
        "pipeline_stage_losses": {
            "correct_detection_labels": detection_tp,
            "confirmed_end_to_end": end_to_end_tp,
            "total_losses": stage_loss_total,
            "by_stage": dict(sorted(stage_losses.items())),
        },
        "end_to_end": end_to_end_metrics,
    }
