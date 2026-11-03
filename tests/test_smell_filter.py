import json
from types import SimpleNamespace

import pytest

from research_pipeline.smells.filter import SmellCandidate, filter_candidates, score

CODE = "def f(a, b, c, d, e, g):\n    return a.b.c.d.e()\n"


def _candidate(id_, smell="LongParameterList", code=CODE, path="m.py"):
    return SmellCandidate(id_, smell, path, 1, "pysmell", {"PAR": 6}, code)


class FakeLLM:
    def __init__(self, *answers):
        self.answers, self.users = list(answers), []

    def complete(self, system, user, *, json_mode=False):
        self.users.append(user)
        return SimpleNamespace(raw_response=self.answers.pop(0))


def _verdicts(*items):
    return json.dumps({"verdicts": [{"id": i, "smell": s, "reason": "r"} for i, s in items]})


def test_candidates_on_the_same_code_go_in_one_call():
    llm = FakeLLM(_verdicts(("a", True), ("b", False)))
    results = filter_candidates([_candidate("a"), _candidate("b", "LongMessageChain")], llm)
    assert len(llm.users) == 1 and "a" in llm.users[0] and "LongMessageChain" in llm.users[0]
    assert results == {"a": {"smell": True, "reason": "r"}, "b": {"smell": False, "reason": "r"}}


def test_a_missing_answer_is_an_error_only_for_that_candidate():
    results = filter_candidates([_candidate("a"), _candidate("b")], FakeLLM(_verdicts(("a", False))))
    assert results["a"]["smell"] is False and "error" in results["b"]


def test_invalid_json_is_an_error_for_the_whole_group():
    results = filter_candidates([_candidate("a"), _candidate("b")], FakeLLM("not json"))
    assert all("error" in r for r in results.values())


def test_extra_and_repeated_ids_are_ignored_and_only_a_boolean_counts():
    answer = json.dumps({"verdicts": [{"id": "a", "smell": "false", "reason": "r"},
                                      {"id": "a", "smell": True, "reason": "second"},
                                      {"id": "zzz", "smell": True, "reason": "r"}]})
    results = filter_candidates([_candidate("a")], FakeLLM(answer))
    assert results == {"a": {"smell": "false", "reason": "r"}}


def test_no_code_is_skipped_and_answered_candidates_are_not_asked_again():
    llm = FakeLLM()
    done = {"a": {"smell": True, "reason": "r"}}
    results = filter_candidates([_candidate("a"), _candidate("b", code="")], llm, done=done)
    assert llm.users == [] and results == {"a": done["a"], "b": {"skipped": "no code"}}


def test_score_keeps_every_candidate_the_llm_did_not_reject():
    candidates = [_candidate("tp"), _candidate("fp"), _candidate("err"), _candidate("gone")]
    labels = {k: ("LongParameterList", v) for k, v in
              {"tp": 1, "fp": 0, "err": 0, "gone": 1, "missed": 1, "neg": 0}.items()}
    results = {"tp": {"smell": True, "reason": ""}, "fp": {"smell": False, "reason": ""},
               "err": {"error": "x"}, "gone": {"smell": False, "reason": ""}}
    report = score(candidates, labels, results)
    assert report["tool"] == pytest.approx({"tp": 2, "fp": 2, "fn": 1, "precision": 0.5, "recall": 2 / 3, "f1": 4 / 7})
    assert report["tool_llm"] == pytest.approx({"tp": 1, "fp": 1, "fn": 2, "precision": 0.5, "recall": 1 / 3,
                                                "f1": 0.4})
    assert report["llm_errors"] == 1 and report["no_code"] == 0
    assert report["per_smell"]["LongParameterList"]["tool_llm"]["fn"] == 2


def test_score_without_candidates_has_no_precision():
    report = score([], {"x": ("LongMethod", 1)}, {})
    assert report["tool"]["precision"] is None and report["tool"]["recall"] == 0.0
