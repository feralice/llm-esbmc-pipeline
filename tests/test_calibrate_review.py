from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "scripts")
import calibrate_review as cal


def _item(bug_id: str, project: str, function: str = "f", expression: str = "x // y") -> dict:
    return {"id": bug_id, "file": f"{bug_id}.py", "function": function, "expression": expression,
            "provenance": {"project": project}}


def test_choose_threshold_keeps_every_known_bug() -> None:
    scores = [9.0, 3.0, 7.0, 1.0]
    bugs = ["a", None, "b", None]
    assert cal.choose_threshold(scores, bugs) == 7.0


def test_choose_threshold_uses_the_best_hit_of_each_bug_and_ties_resolve_down() -> None:
    scores = [2.0, 6.0, 6.0]
    bugs = ["a", "a", "b"]
    assert cal.choose_threshold(scores, bugs) == 6.0
    assert cal.choose_threshold([5.0, 5.0], ["a", "b"]) == 5.0


def test_choose_threshold_without_hits_is_zero() -> None:
    assert cal.choose_threshold([9.0], [None]) == 0.0


def test_split_never_shares_a_project() -> None:
    projects = {f"b{i}": f"p{i % 6}" for i in range(18)}
    calibration, held_out = cal.split_by_project(projects, 0.5, seed=1)
    assert calibration and held_out and not calibration & held_out
    assert {projects[b] for b in calibration}.isdisjoint({projects[b] for b in held_out})
    assert calibration | held_out == set(projects)


def test_split_refuses_single_project() -> None:
    with pytest.raises(ValueError, match="project"):
        cal.split_by_project({"a": "p", "b": "p"}, 0.5, seed=0)


def test_label_hypotheses_matches_equivalent_expression_in_the_same_file_and_function() -> None:
    items = [_item("b1", "p1"), _item("b2", "p2", function="g", expression="d[k]")]
    candidates = [
        {"file": "dir/b1.py", "function": "f", "expression": "x//y"},
        {"file": "dir/b1.py", "function": "f", "expression": "z"},
        {"file": "dir/b1.py", "function": "g", "expression": "d[k]"},
        {"file": "dir/b2.py", "function": "g", "expression": "d[k]"},
    ]
    assert cal.label_hypotheses(candidates, items) == ["b1", None, None, "b2"]


def test_table_counts_hypotheses_and_lost_bugs_per_threshold() -> None:
    rows = cal.table([9.0, 4.0, 2.0], ["a", "b", None], thresholds=[0, 5, 10])
    assert rows == [(0, 3, 2, []), (5, 1, 1, ["b"]), (10, 0, 0, ["a", "b"])]
