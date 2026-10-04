from __future__ import annotations

import json

import pytest

from research_pipeline.v2_evaluator import (
    _bug_detection_metrics,
    evaluate_detection,
    expressions_equivalent,
)
from research_pipeline.verify.candidate import Candidate


def test_detection_counts_one_true_positive_and_ignores_duplicates_by_location(tmp_path) -> None:
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
    correct = Candidate(str(source), "f", "division_by_zero")
    false_positive = Candidate(str(source), "f", "out_of_bounds")
    metrics = evaluate_detection(candidates=[correct, false_positive],
        ground_truth_path=tmp_path / "ground_truths.json",
    )

    assert metrics["detection"]["tp"] == 1
    assert metrics["detection"]["fp"] == 0
    assert metrics["detection"]["fn"] == 0


def test_v2_reports_location_whatever_the_category_label(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    source = detection / "bug.py"
    source.write_text("def f(x: int) -> int:\n    return 1 // x\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "b1", "categories": ["division_by_zero"]}]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [{
            "id": "b1", "detection_file": "detection/bug.py", "function": "f",
            "expression": "1 // x", "harness_file": "bugs/bug.py",
            "categories": ["division_by_zero"],
        }]}),
        encoding="utf-8",
    )
    wrong_category = Candidate(str(source), "f", "none_misuse", expression="1 // x")

    metrics = evaluate_detection(candidates=[wrong_category],
        ground_truth_path=tmp_path / "ground_truths.json",
    )

    assert metrics["detection"]["tp"] == 1
    assert metrics["detection"]["fp"] == 0
    assert metrics["detection"]["fn"] == 0
    assert metrics["bug_detection"]["file"]["tp"] == 1
    assert metrics["bug_detection"]["location"]["tp"] == 1
    assert metrics["bug_detection"]["expression"]["tp"] == 1


def test_v2_excludes_patch_context_items_from_detection_metrics(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    first = detection / "first.py"
    second = detection / "second.py"
    source = "def f(x: int) -> int:\n    return 1 // x\n"
    first.write_text(source, encoding="utf-8")
    second.write_text(source, encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [
            {"id": "b1", "categories": ["division_by_zero"]},
            {"id": "b2", "categories": ["assertion_violation"]},
        ]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({
            "evaluation_policy": {"patch_context_items": ["b2"]},
            "items": [
                {"id": "b1", "detection_file": "detection/first.py", "categories": ["division_by_zero"]},
                {"id": "b2", "detection_file": "detection/second.py", "categories": ["assertion_violation"]},
            ],
        }),
        encoding="utf-8",
    )
    candidate = Candidate(str(first), "f", "division_by_zero")
    metrics = evaluate_detection(candidates=[candidate],
        ground_truth_path=tmp_path / "ground_truths.json",
    )
    assert metrics["excluded_patch_context_items"] == 1
    assert metrics["detection"]["tp"] == 1
    assert metrics["detection"]["fn"] == 0


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
    metrics = evaluate_detection(candidates=[], ground_truth_path=tmp_path / "ground_truths.json",
        rejected_findings=[{
            "file": str(source), "category": "division_by_zero",
            "finding_type": "llm_false_positive",
        }],
    )
    assert metrics["detection"]["fp"] == 1




@pytest.mark.parametrize("expected, found, same", [
    ("float(a)/float(b)", "float(a) / float(b)", True),
    ("':' not in self._url", "if ':' not in self._url:", True),
    ("x[0]", "return x[0]", True),
    ("'open ' + s[5:]", "s[5:]", True),
    ("self.iterable = iterable", "self.set_postfix(refresh=False)", False),
    ("a // b", "a // c", False),
    ("self.iterable = iterable", "iterable", False),
    ("self.x + 1", "self.x", False),
    ("self.a.b[0]", "if self.a.b[0]:", True),
    ("", "a // b", False),
])
def test_expressions_equivalent(expected, found, same):
    assert expressions_equivalent(expected, found) is same


def test_equivalent_expression_metric_sits_beside_the_exact_one(tmp_path):
    item = {"detection_file": "d.py", "function": "f", "expression": "float(a)/float(b)",
            "categories": ["division_by_zero"]}
    base = str((tmp_path / "d.py").resolve())
    same_function = {"file": base, "function": "f", "expression": "float(a) / float(b)", "category": "x"}
    other_function = {"file": base, "function": "g", "expression": "float(a)/float(b)", "category": "x"}
    metrics = _bug_detection_metrics([item], [same_function, other_function], tmp_path)
    assert metrics["expression"]["tp"] == 0
    assert metrics["expression_equivalent"]["tp"] == 1
    assert metrics["expression_equivalent"]["fp"] == 1
