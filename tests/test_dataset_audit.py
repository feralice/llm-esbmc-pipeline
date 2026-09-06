import json

from research_pipeline.dataset_audit import audit_dataset, write_dataset_audit


def test_dataset_audit_detects_leak_and_hidden_oracle(tmp_path) -> None:
    bugs = tmp_path / "bugs"
    bugs.mkdir()
    (bugs / "sample.py").write_text(
        """def calculate_buggy(x: int) -> int:
    # Real bug: the fix changes this expression.
    return x + 1

def main() -> None:
    assert calculate_buggy(0) == 0

main()
""",
        encoding="utf-8",
    )
    gt = tmp_path / "ground_truths.json"
    gt.write_text(json.dumps({"items": [{
        "id": "one", "file": "sample.py", "function": "calculate_buggy",
        "categories": ["invalid_precondition"], "expression": "result == expected",
        "verifiable": True
    }]}), encoding="utf-8")

    report = audit_dataset(gt)

    assert report["labels_not_grounded_in_target"] == 1
    assert report["issue_counts"]["label_leak_in_function_name"] == 1
    assert report["issue_counts"]["label_leak_in_comments"] == 1
    assert report["issue_counts"]["oracle_hidden_in_skipped_main"] == 1


def test_dataset_audit_clean_target_is_grounded(tmp_path) -> None:
    bugs = tmp_path / "bugs"
    bugs.mkdir()
    (bugs / "sample.py").write_text(
        "def divide(a: int, b: int) -> int:\n    return a // b\n", encoding="utf-8"
    )
    gt = tmp_path / "ground_truths.json"
    gt.write_text(json.dumps({"items": [{
        "id": "one", "file": "sample.py", "function": "divide",
        "categories": ["division_by_zero"], "expression": "a // b", "verifiable": True
    }]}), encoding="utf-8")
    report = audit_dataset(gt)
    assert report["labels_grounded_in_target"] == 1
    assert report["issues"] == []


def test_write_dataset_audit_round_trips(tmp_path) -> None:
    output = write_dataset_audit({"labels_checked": 0}, tmp_path / "audit.json")
    assert json.loads(output.read_text(encoding="utf-8"))["labels_checked"] == 0


def test_dataset_audit_accepts_module_level_grounding(tmp_path) -> None:
    detection = tmp_path / "detection"
    bugs = tmp_path / "bugs"
    detection.mkdir()
    bugs.mkdir()
    (detection / "constants.py").write_text("pi: float = 3.14\n", encoding="utf-8")
    (bugs / "constants.py").write_text("pi: float = 3.14\n", encoding="utf-8")
    gt = tmp_path / "ground_truths.json"
    gt.write_text(json.dumps({"items": [{
        "id": "module-1", "file": "constants.py",
        "function": "module-level constants", "categories": ["incorrect_result"],
        "expression": "pi: float = 3.14", "verifiable": True
    }]}), encoding="utf-8")

    report = audit_dataset(gt)

    assert report["module_level_labels"] == 1
    assert report["labels_grounded_in_target"] == 1
    assert report["issues"] == []
