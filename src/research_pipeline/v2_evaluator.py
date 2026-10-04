"""Detection metrics for the V2 real-bug experiment.

The detector never reads these artifacts. Evaluation happens after the run, using the manifest
only to map detection sources to the known labels, which prevents oracle leakage into prompts.
"""

from __future__ import annotations

import ast
import json
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


# Ground-truth failure kinds the ESBMC can confirm (dataset/README.md, campo failure_kind).
_REACHES_ESBMC = {"excecao_local": True, "excecao_modelavel": True,
                  "excecao_nao_modelavel": False, "resultado_errado": False, "incerto": None}


def should_reach_esbmc(item: dict) -> bool | None:
    """Whether the bug violates a property ESBMC checks on its own; None when unlabelled or uncertain."""
    if "failure_kind" not in item:
        return None
    kind = str(item["failure_kind"])
    if kind not in _REACHES_ESBMC:
        raise ValueError(f"unknown failure_kind {kind!r} in item {item.get('id')}")
    return _REACHES_ESBMC[kind]


_STATEMENT_PREFIXES = ("if ", "elif ", "while ", "return ", "assert ")


def _normalized(text: str) -> ast.AST | None:
    """One expression or statement, ignoring spacing, a leading keyword and a trailing colon."""
    text = text.strip().removesuffix(":").strip()
    for prefix in _STATEMENT_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    try:
        return ast.parse(text, mode="eval").body
    except SyntaxError:
        try:
            return ast.parse(text).body[0]
        except (SyntaxError, IndexError):
            return None


def _is_reference(node: ast.expr) -> bool:
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, (ast.Name, ast.Constant))


def _subexpressions(node: ast.AST) -> set[str]:
    # A bare name, attribute chain or literal would match any expression that mentions it.
    return {ast.dump(n) for n in ast.walk(node) if isinstance(n, ast.expr) and not _is_reference(n)}


def expressions_equivalent(expected: str, found: str) -> bool:
    """Same expression up to spacing and ``if``/``return``-style wrapping, or one is a
    subexpression of the other (part of the buggy expression, or the statement around it)."""
    a, b = _normalized(expected), _normalized(found)
    if a is None or b is None:
        return False
    return ast.dump(a) == ast.dump(b) or ast.dump(a) in _subexpressions(b) or ast.dump(b) in _subexpressions(a)


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def _triage_metrics(expected: list[dict], generated: list[dict]) -> dict:
    """Did detection send to ESBMC exactly the found bugs that ESBMC can confirm?

    Only bugs found as in ``expression_equivalent`` count, so a finding about another line of the same
    function says nothing about the bug. A bug is "sent" when any matching finding was sent.
    """
    counts = {"should_send": {"sent": 0, "held": 0}, "should_hold": {"sent": 0, "held": 0}, "uncertain_label": 0}
    for item in expected:
        found = [c for c in generated if c["file"] == item["file"] and c["function"] in item["functions"]
                 and (not item["expression"] or expressions_equivalent(item["expression"], c["expression"]))]
        if not found:
            continue
        if item["reaches_esbmc"] is None:
            counts["uncertain_label"] += 1
            continue
        group = counts["should_send" if item["reaches_esbmc"] else "should_hold"]
        group["sent" if any(c["sent"] for c in found) else "held"] += 1
    send, hold = counts["should_send"], counts["should_hold"]
    return {
        **counts,
        "sent_when_should": _ratio(send["sent"], send["sent"] + send["held"]),
        "held_when_should": _ratio(hold["held"], hold["sent"] + hold["held"]),
    }


def _bug_detection_metrics(
    expected_items: list[dict], candidates: list, base: Path,
    rejected_findings: list[dict] | None = None,
) -> dict:
    """Measure case localization and the triage decision."""
    expected = [
        {
            "file": str((base / item["detection_file"]).resolve()),
            # "gamma / lgamma": the same bug appears in each listed function.
            "functions": {part.strip() for part in str(item.get("function", "")).split("/") if part.strip()},
            "expression": str(item.get("expression", "")),
            "reaches_esbmc": should_reach_esbmc(item),
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
            # Candidates are what detection sent to ESBMC; rejected findings were held back.
            "sent": not isinstance(candidate, dict) or bool(candidate.get("sent", True)),
        }
        for candidate in [*candidates, *({**r, "sent": False} for r in (rejected_findings or []))]
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
    equivalent_metrics = count_matches(
        lambda item, candidate: (
            candidate["file"] == item["file"]
            and candidate["function"] in item["functions"]
            and expressions_equivalent(item["expression"], candidate["expression"])
        )
    )
    detection_metrics = count_matches(matches_primary_location)
    triage = _triage_metrics(expected, generated)
    return {
        "detection": detection_metrics,
        "file": file_metrics,
        "location": location_metrics,
        "expression": expression_metrics,
        "expression_equivalent": equivalent_metrics,
        "triage": triage,
    }


def evaluate_detection(
    *,
    candidates: list,
    ground_truth_path: str | Path,
    manifest_path: str | Path | None = None,
    evaluated_sources: list[str | Path] | None = None,
    rejected_findings: list[dict] | None = None,
) -> dict:
    """Detection by location (file, function, expression) and the triage of what goes to ESBMC."""
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
    location = _bug_detection_metrics(evaluated_items, candidates, base, rejected_findings)
    return {
        "detection_scope": "items without patch context",
        "excluded_patch_context_items": len(patch_context_ids),
        # Primary location match (file, function and, when labelled, the exact expression).
        "detection": location["detection"],
        # Whether detection sent to ESBMC the found bugs ESBMC can confirm, and held back the rest.
        "triage": location["triage"],
        "bug_detection": location,
    }
