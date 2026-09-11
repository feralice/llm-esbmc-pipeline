from __future__ import annotations

import json

from research_pipeline.scan.pipeline import ScanCandidate, ScanCaseResult
from research_pipeline.v2_evaluator import evaluate_v2_results


def test_v2_metrics_separate_detection_synthesis_and_end_to_end(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    source = detection / "bug.py"
    source.write_text("def f(x: int) -> int:\n    return 1 // x\n", encoding="utf-8")
    (tmp_path / "bugs").mkdir()
    (tmp_path / "bugs" / "bug.py").write_text("assert False\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "b1", "categories": ["division_by_zero"]}]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [{
            "id": "b1", "detection_file": "detection/bug.py",
            "harness_file": "bugs/bug.py", "categories": ["division_by_zero"],
        }]}),
        encoding="utf-8",
    )
    correct = ScanCandidate(str(source), "f", "division_by_zero")
    false_positive = ScanCandidate(str(source), "f", "out_of_bounds")
    results = [
        ScanCaseResult(correct, "confirmed_on_abstraction", compat_verdict="ok"),
        ScanCaseResult(false_positive, "confirmed_on_abstraction", compat_verdict="ok"),
    ]

    metrics = evaluate_v2_results(
        candidates=[correct, false_positive],
        results=results,
        ground_truth_path=tmp_path / "ground_truths.json",
    )

    assert metrics["detection"]["tp"] == 1
    assert metrics["detection"]["fp"] == 1
    assert metrics["detection"]["fn"] == 0
    assert metrics["synthesis_given_correct_detection"]["confirmed_on_abstraction"] == 1
    assert metrics["end_to_end"] == {
        "tp": 1, "fp": 1, "fn": 0,
        "precision": 0.5, "recall": 1.0, "f1": 2 / 3,
    }


def test_over_restricted_is_not_counted_as_confirmation(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    source = detection / "bug.py"
    source.write_text("def f(x: int) -> int:\n    return x\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "b1", "categories": ["invalid_precondition"]}]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [{
            "id": "b1", "detection_file": "detection/bug.py",
            "harness_file": "bugs/bug.py", "categories": ["invalid_precondition"],
        }]}),
        encoding="utf-8",
    )
    candidate = ScanCandidate(str(source), "f", "invalid_precondition")
    result = ScanCaseResult(candidate, "over_restricted", compat_verdict="ok")

    metrics = evaluate_v2_results(
        candidates=[candidate], results=[result],
        ground_truth_path=tmp_path / "ground_truths.json",
    )
    assert metrics["synthesis_given_correct_detection"]["over_restricted"] == 1
    assert metrics["end_to_end"]["tp"] == 0
    assert metrics["end_to_end"]["fn"] == 1


def test_ast_rejection_remains_a_detection_false_positive(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    source = detection / "clean.py"
    source.write_text("def f(x: int) -> int:\n    return x\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "c1", "categories": []}]}), encoding="utf-8"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [{
            "id": "c1", "detection_file": "detection/clean.py",
            "harness_file": "bugs/clean.py", "categories": [],
        }]}),
        encoding="utf-8",
    )
    metrics = evaluate_v2_results(
        candidates=[], results=[], ground_truth_path=tmp_path / "ground_truths.json",
        rejected_findings=[{
            "file": str(source), "category": "division_by_zero",
            "finding_type": "llm_false_positive",
        }],
    )
    assert metrics["detection"]["fp"] == 1


def test_stage_losses_account_for_correct_detection_labels(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    first = detection / "first.py"
    second = detection / "second.py"
    source = "def f(x: int) -> int:\n    return 1 // x\n"
    first.write_text(source, encoding="utf-8")
    second.write_text(source, encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "b1", "categories": ["division_by_zero"]},
                               {"id": "b2", "categories": ["division_by_zero"]}]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [
            {"id": "b1", "detection_file": "detection/first.py", "categories": ["division_by_zero"]},
            {"id": "b2", "detection_file": "detection/second.py", "categories": ["division_by_zero"]},
        ]}),
        encoding="utf-8",
    )
    correct_but_safe = ScanCandidate(str(first), "f", "division_by_zero")
    rejected_correct = {
        "file": str(second),
        "category": "division_by_zero",
        "finding_type": "llm_false_positive",
        "reason": "invalid_expression_syntax",
    }

    metrics = evaluate_v2_results(
        candidates=[correct_but_safe],
        results=[ScanCaseResult(correct_but_safe, "safe_driver")],
        ground_truth_path=tmp_path / "ground_truths.json",
        rejected_findings=[rejected_correct],
    )

    losses = metrics["pipeline_stage_losses"]
    assert losses["correct_detection_labels"] == 2
    assert losses["confirmed_end_to_end"] == 0
    assert losses["total_losses"] == 2
    assert losses["by_stage"] == {"grounding": 1, "verification": 1}
