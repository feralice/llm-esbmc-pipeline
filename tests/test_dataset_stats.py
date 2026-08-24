import json

from research_pipeline.dataset_stats import build_dataset_statistics, write_dataset_statistics


def test_dataset_statistics_support_multilabel_and_annotations(tmp_path) -> None:
    bugs = tmp_path / "bugs"
    bugs.mkdir()
    (bugs / "sample.py").write_text(
        """def sample(a: int, b: int) -> int:
    if a > 0 and b > 0:
        return a
    return b
""",
        encoding="utf-8",
    )
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": [{
        "file": "sample.py", "function": "sample", "verifiable": True,
        "categories": ["invalid_precondition", "variable_misuse"]
    }]}), encoding="utf-8")

    report = build_dataset_statistics(ground_truth)

    assert report["case_count"] == 1
    assert report["label_count"] == 2
    assert report["functions_missing_type_annotations"] == 0
    assert report["overall"]["cyclomatic_complexity"]["mean"] == 3.0
    assert report["per_category"]["variable_misuse"]["functions"] == 1


def test_write_dataset_statistics_round_trips_json(tmp_path) -> None:
    output = write_dataset_statistics({"case_count": 0}, tmp_path / "stats.json")
    assert json.loads(output.read_text(encoding="utf-8"))["case_count"] == 0
