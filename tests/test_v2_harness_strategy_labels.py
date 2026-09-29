"""V2 ground truth answers in harness strategies, the detector's four categories."""
from __future__ import annotations

import json
from pathlib import Path

from research_pipeline.v2_evaluator import evaluate_detection
from research_pipeline.verify.candidate import Candidate


def _dataset(tmp_path: Path, items: list[dict]) -> Path:
    (tmp_path / "detection").mkdir()
    (tmp_path / "bugs").mkdir()
    for item in items:
        (tmp_path / "detection" / f"{item['id']}.py").write_text(
            "def f(values, i):\n    return values[i]\n", encoding="utf-8")
        (tmp_path / "bugs" / f"{item['id']}.py").write_text("assert False\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": item["id"], "categories": item["categories"]} for item in items]}),
        encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"items": [
        {"detection_file": f"detection/{item['id']}.py", "harness_file": f"bugs/{item['id']}.py",
         "function": "f", "expression": "values[i]", **item}
        for item in items]}), encoding="utf-8")
    return tmp_path / "ground_truths.json"


def _candidate(tmp_path: Path, key: str, strategy: str) -> Candidate:
    return Candidate(str(tmp_path / "detection" / f"{key}.py"), "f", strategy, expression="values[i]")


def test_strategy_answer_matches_the_strategy_ground_truth(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [
        {"id": "oob", "categories": ["out_of_bounds"], "harness_strategies": ["native_runtime"]}])
    found = _candidate(tmp_path, "oob", "native_runtime")

    metrics = evaluate_detection(candidates=[found], ground_truth_path=ground_truth)

    assert (metrics["detection"]["tp"], metrics["detection"]["fn"]) == (1, 0)
    assert metrics["bug_detection"]["category_given_location"]["tp"] == 1


def test_any_accepted_strategy_counts_once_for_a_multi_label_item(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{
        "id": "wrong_value", "categories": ["invalid_precondition", "none_misuse"],
        "harness_strategies": ["explicit_assertion", "differential_assertion"]}])
    found = _candidate(tmp_path, "wrong_value", "differential_assertion")

    metrics = evaluate_detection(candidates=[found], ground_truth_path=ground_truth)

    assert metrics["expected_labels"] == 1
    assert metrics["bug_detection"]["category_given_location"]["tp"] == 1


def test_wrong_strategy_is_a_miss(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [
        {"id": "oob", "categories": ["out_of_bounds"], "harness_strategies": ["native_runtime"]}])
    found = _candidate(tmp_path, "oob", "differential_assertion")

    metrics = evaluate_detection(candidates=[found], ground_truth_path=ground_truth)

    assert metrics["detection"]["tp"] == 1
    assert metrics["bug_detection"]["category_given_location"]["tp"] == 0


def test_items_without_strategies_keep_one_label_per_category(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{"id": "legacy", "categories": ["division_by_zero", "invalid_precondition"]}])

    metrics = evaluate_detection(candidates=[], ground_truth_path=ground_truth)

    assert metrics["expected_labels"] == 2


def test_function_label_with_alternatives_accepts_either_function(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{
        "id": "twin", "categories": ["incorrect_result"],
        "harness_strategies": ["explicit_assertion"], "function": "gamma / lgamma"}])
    found = Candidate(str(tmp_path / "detection" / "twin.py"), "lgamma", "explicit_assertion",
                          expression="values[i]")

    metrics = evaluate_detection(candidates=[found], ground_truth_path=ground_truth)

    assert metrics["bug_detection"]["location"]["tp"] == 1
    assert metrics["bug_detection"]["category_given_location"]["tp"] == 1
