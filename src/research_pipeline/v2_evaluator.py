"""Detection metrics for the V2 real-bug experiment.

The detector never reads these artifacts. Evaluation happens after the run, using the manifest
only to map detection sources to the known labels, which prevents oracle leakage into prompts.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


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


def evaluate_detection(
    *,
    candidates: list,
    ground_truth_path: str | Path,
    manifest_path: str | Path | None = None,
    evaluated_sources: list[str | Path] | None = None,
    rejected_findings: list[dict] | None = None,
) -> dict:
    """Detection by category label (the original metric) and by location (file, function, expression)."""
    gt_path = Path(ground_truth_path)
    manifest_file = Path(manifest_path) if manifest_path else gt_path.parent / "manifest.json"
    gt_items = json.loads(gt_path.read_text(encoding="utf-8")).get("items", [])
    manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest_items = manifest_payload.get("items", [])
    patch_context_ids = {
        str(item) for item in manifest_payload.get("evaluation_policy", {}).get("patch_context_items", [])
    }
    if {str(i.get("id")) for i in gt_items} != {str(i.get("id")) for i in manifest_items}:
        raise ValueError("ground truth and V2 manifest contain different case IDs")

    base = manifest_file.parent
    allowed = {str(Path(p).resolve()) for p in evaluated_sources} if evaluated_sources is not None else None
    evaluated_items = [
        item for item in manifest_items
        if str(item.get("id")) not in patch_context_ids
        and (allowed is None or str((base / item["detection_file"]).resolve()) in allowed)
    ]
    slots_by_file: dict[str, list[frozenset[str]]] = {}
    for item in evaluated_items:
        slots_by_file.setdefault(str((base / item["detection_file"]).resolve()), []).extend(_expected_slots(item))
    expected = Counter((source, _slot_key(slot)) for source, slots in slots_by_file.items() for slot in slots)

    def answer_signature(file: str, category: str) -> tuple[str, str]:
        source, category = _signature(file, category)
        slot = next((s for s in slots_by_file.get(source, []) if category in s), None)
        return (source, _slot_key(slot)) if slot else (source, category)

    generated = Counter(answer_signature(c.file, c.category) for c in candidates)
    generated.update(answer_signature(str(i["file"]), str(i["category"])) for i in (rejected_findings or []))
    tp = sum((expected & generated).values())
    fp = sum((generated - expected).values())
    fn = sum((expected - generated).values())
    location = _bug_detection_metrics(evaluated_items, candidates, base, rejected_findings)
    return {
        "detection_scope": "items without patch context",
        "excluded_patch_context_items": len(patch_context_ids),
        "expected_labels": sum(expected.values()),
        # Primary location match (file, function and, when labelled, the exact expression).
        "detection": location["detection"],
        # Category label per detection file, ignoring where in the file it points.
        "category_label": {"tp": tp, "fp": fp, "fn": fn, **_prf(tp, fp, fn)},
        "bug_detection": location,
    }
