"""V2 triage: did detection send to ESBMC the found bugs ESBMC can confirm, and hold back the rest?"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_pipeline.v2_evaluator import evaluate_detection, should_reach_esbmc
from research_pipeline.verify.candidate import Candidate


def _dataset(tmp_path: Path, items: list[dict]) -> Path:
    (tmp_path / "detection").mkdir()
    for item in items:
        (tmp_path / "detection" / f"{item['id']}.py").write_text(
            "def f(values, i):\n    return values[i]\n", encoding="utf-8")
    full = [{"categories": ["unclassified"], "detection_file": f"detection/{item['id']}.py",
             "function": "f", "expression": "values[i]", **item} for item in items]
    (tmp_path / "ground_truths.json").write_text(json.dumps({"items": full}), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"items": full}), encoding="utf-8")
    return tmp_path / "ground_truths.json"


def _sent(tmp_path: Path, key: str) -> Candidate:
    return Candidate(str(tmp_path / "detection" / f"{key}.py"), "f", expression="values[i]")


def _held(tmp_path: Path, key: str) -> dict:
    return {"file": str(tmp_path / "detection" / f"{key}.py"), "function": "f",
            "expression": "values[i]", "finding_type": "suspected_bug"}


def test_sending_a_crashing_bug_and_holding_a_wrong_result_are_both_right(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{"id": "crash", "failure_kind": "excecao_local"},
                                       {"id": "value", "failure_kind": "resultado_errado"}])

    triage = evaluate_detection(candidates=[_sent(tmp_path, "crash")], ground_truth_path=ground_truth,
                                rejected_findings=[_held(tmp_path, "value")])["triage"]

    assert triage["should_send"] == {"sent": 1, "held": 0}
    assert triage["should_hold"] == {"sent": 0, "held": 1}
    assert (triage["sent_when_should"], triage["held_when_should"]) == (1.0, 1.0)


def test_holding_a_crashing_bug_and_sending_a_wrong_result_are_both_wrong(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{"id": "crash", "failure_kind": "excecao_modelavel"},
                                       {"id": "value", "failure_kind": "excecao_nao_modelavel"}])

    triage = evaluate_detection(candidates=[_sent(tmp_path, "value")], ground_truth_path=ground_truth,
                                rejected_findings=[_held(tmp_path, "crash")])["triage"]

    assert (triage["sent_when_should"], triage["held_when_should"]) == (0.0, 0.0)


def test_one_sent_finding_is_enough_for_a_bug_to_count_as_sent(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{"id": "crash", "failure_kind": "excecao_local"}])

    triage = evaluate_detection(candidates=[_sent(tmp_path, "crash")], ground_truth_path=ground_truth,
                                rejected_findings=[_held(tmp_path, "crash")])["triage"]

    assert triage["should_send"] == {"sent": 1, "held": 0}


def test_missed_bugs_and_uncertain_labels_stay_out_of_the_triage(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{"id": "missed", "failure_kind": "excecao_local"},
                                       {"id": "unsure", "failure_kind": "incerto"}])

    triage = evaluate_detection(candidates=[_sent(tmp_path, "unsure")], ground_truth_path=ground_truth)["triage"]

    assert triage["should_send"] == {"sent": 0, "held": 0}
    assert triage["uncertain_label"] == 1
    assert triage["sent_when_should"] is None


@pytest.mark.parametrize(("item", "expected"), [
    ({"failure_kind": "excecao_local"}, True),
    ({"failure_kind": "excecao_modelavel"}, True),
    ({"failure_kind": "resultado_errado"}, False),
    ({"failure_kind": "excecao_nao_modelavel"}, False),
    ({"failure_kind": "incerto"}, None),
    ({"categories": ["none_misuse"]}, None),
])
def test_only_the_failure_kind_decides_whether_a_bug_should_reach_esbmc(item, expected) -> None:
    assert should_reach_esbmc(item) is expected


def test_function_label_with_alternatives_accepts_either_function(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{"id": "twin", "function": "gamma / lgamma"}])
    found = Candidate(str(tmp_path / "detection" / "twin.py"), "lgamma", expression="values[i]")

    metrics = evaluate_detection(candidates=[found], ground_truth_path=ground_truth)

    assert metrics["bug_detection"]["location"]["tp"] == 1


def test_a_finding_on_another_line_of_the_same_function_does_not_count_for_the_bug(tmp_path) -> None:
    ground_truth = _dataset(tmp_path, [{"id": "crash", "failure_kind": "excecao_local"}])
    elsewhere = Candidate(str(tmp_path / "detection" / "crash.py"), "f", expression="len(values)")

    triage = evaluate_detection(candidates=[elsewhere], ground_truth_path=ground_truth)["triage"]

    assert triage["should_send"] == {"sent": 0, "held": 0}


def test_an_unknown_failure_kind_is_an_error_not_an_uncertain_label() -> None:
    with pytest.raises(ValueError, match="excecao_locl"):
        should_reach_esbmc({"id": "typo", "failure_kind": "excecao_locl"})
