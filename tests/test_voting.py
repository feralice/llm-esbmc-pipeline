from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_pipeline.voting import aggregate_votes, write_vote_report


def _write_eval(
    model_dir: Path,
    stem: str,
    findings: list[dict],
    *,
    expected_bugs: list[dict] | None = None,
) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "file": f"{stem}.py",
        "expected_bugs": expected_bugs or [],
        "generated_bugs": findings,
    }
    (model_dir / f"{stem}_eval.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_aggregate_votes_counts_distinct_models_and_applies_threshold(tmp_path: Path) -> None:
    model_a = tmp_path / "model-a"
    model_b = tmp_path / "model-b"
    model_c = tmp_path / "model-c"
    shared = {
        "function": "read_item",
        "category": "out_of_bounds",
        "expression": "items[i]",
        "line": 2,
    }
    _write_eval(model_a, "sample", [shared, shared])
    _write_eval(model_b, "sample", [shared])
    _write_eval(
        model_c,
        "sample",
        [{"function": "read_item", "category": "division_by_zero"}],
    )

    result = aggregate_votes([model_a, model_b, model_c], min_votes=2)

    assert result["model_count"] == 3
    assert result["candidate_count"] == 2
    assert result["selected_count"] == 1
    selected = next(item for item in result["candidates"] if item["selected"])
    assert selected["votes"] == 2
    assert selected["models"] == ["model-a", "model-b"]
    assert len(selected["evidence_by_model"]["model-a"]) == 2


def test_aggregate_votes_does_not_read_ground_truth_verdicts(tmp_path: Path) -> None:
    model_a = tmp_path / "model-a"
    _write_eval(
        model_a,
        "sample",
        [],
        expected_bugs=[{"function": "hidden_truth", "category": "out_of_bounds"}],
    )

    result = aggregate_votes([model_a], min_votes=1)

    assert result["candidate_count"] == 0
    assert result["selected_count"] == 0


def test_aggregate_votes_rejects_invalid_threshold(tmp_path: Path) -> None:
    model_a = tmp_path / "model-a"
    _write_eval(model_a, "sample", [])

    with pytest.raises(ValueError, match="min_votes"):
        aggregate_votes([model_a], min_votes=2)


def test_write_vote_report_round_trips_json(tmp_path: Path) -> None:
    report = {"model_count": 1, "candidates": []}
    output = write_vote_report(report, tmp_path / "nested" / "votes.json")

    assert json.loads(output.read_text(encoding="utf-8")) == report


def _write_smell_eval(model_dir: Path, stem: str, smells: list[dict]) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = {"file": f"{stem}.py", "expected_smells": [], "generated_smells": smells}
    (model_dir / f"{stem}_eval.json").write_text(json.dumps(payload), encoding="utf-8")


def test_aggregate_votes_kind_smells_reads_generated_smells(tmp_path: Path) -> None:
    model_a = tmp_path / "model-a"
    model_b = tmp_path / "model-b"
    smell = {"function": "handle_request", "category": "long_method"}
    _write_smell_eval(model_a, "sample", [smell])
    _write_smell_eval(model_b, "sample", [smell])

    result = aggregate_votes([model_a, model_b], min_votes=2, kind="smells")

    assert result["candidate_count"] == 1
    selected = result["candidates"][0]
    assert selected["category"] == "long_method"
    assert selected["selected"] is True


def test_aggregate_votes_kind_smells_ignores_generated_bugs(tmp_path: Path) -> None:
    model_a = tmp_path / "model-a"
    _write_eval(model_a, "sample", [{"function": "f", "category": "division_by_zero"}])

    result = aggregate_votes([model_a], min_votes=1, kind="smells")

    assert result["candidate_count"] == 0


def test_aggregate_votes_rejects_invalid_kind(tmp_path: Path) -> None:
    model_a = tmp_path / "model-a"
    _write_eval(model_a, "sample", [])

    with pytest.raises(ValueError, match="kind"):
        aggregate_votes([model_a], min_votes=1, kind="typo")
