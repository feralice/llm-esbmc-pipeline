import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location("v2_judge", Path(__file__).resolve().parents[1] / "scripts/v2_judge.py")
v2_judge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2_judge)


def test_the_reply_gives_one_score_per_hypothesis():
    reply = json.dumps({"verdicts": [{"index": 0, "real": True, "confidence": 0.9, "input": "k=0"},
                                     {"index": 1, "real": False, "confidence": 0.8}]})
    assert v2_judge.parse_scores(reply, 2) == [0.9, 0.2]


def test_a_missing_or_broken_verdict_keeps_the_hypothesis():
    assert v2_judge.parse_scores("not json", 2) == [None, None]
    assert v2_judge.parse_scores(json.dumps({"verdicts": [{"index": 1, "real": True, "confidence": 2, "input": "x=0"}]}), 2) == [None, 1.0]


def test_a_real_verdict_without_a_concrete_input_counts_half():
    reply = json.dumps({"verdicts": [{"index": 0, "real": True, "confidence": 0.9, "input": ""}]})
    assert v2_judge.parse_scores(reply, 1) == [0.45]


def test_metrics_keep_the_hypotheses_above_the_threshold():
    rows = [{"bug": "a", "at_line": True, "score": 0.9}, {"bug": "a", "at_line": False, "score": 0.1},
            {"bug": "b", "at_line": True, "score": 0.3}, {"bug": "c", "at_line": False, "score": None}]
    m = v2_judge.metrics(rows, 0.5)
    assert m == {"threshold": 0.5, "kept": 2, "bugs_at_line": 1, "precision": 0.5}
    assert v2_judge.metrics(rows, 0.0)["bugs_at_line"] == 2
