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


def test_pysmell_candidates_are_the_items_either_heuristic_reported(tmp_path, monkeypatch, capsys):
    import sys

    sys.path.insert(0, "scripts")
    import smell_filter_pysmell as script

    rows = [{"id": "p1", "smell": "LongParameterList", "label": 1, "path": "a.py", "line": 3, "snippet": "def f(): pass",
             "snippet_start": 3, "tool_experience_based": 1, "tool_statistics_based": 0, "metrics": {"PAR": 9}},
            {"id": "p2", "smell": "LongMethod", "label": 0, "path": "a.py", "line": 9, "snippet": None,
             "tool_experience_based": 0, "tool_statistics_based": 1, "metrics": {}},
            {"id": "p3", "smell": "LongMethod", "label": 1, "path": "b.py", "line": 1,
             "tool_experience_based": 0, "tool_statistics_based": 0}]
    candidates, labels = script.pysmell_candidates(rows)
    assert [(c.id, c.tool, c.code) for c in candidates] == [("p1", "pysmell:experience", "def f(): pass"),
                                                          ("p2", "pysmell:statistics", "")]
    assert labels == {"p1": ("LongParameterList", 1), "p2": ("LongMethod", 0), "p3": ("LongMethod", 1)}
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(tmp_path / "o"), "--sample", "5"])
    assert script.main() == 0 and "Simulação" in capsys.readouterr().out and not (tmp_path / "o").exists()


def test_ruff_reports_become_candidates_with_their_enclosing_code(tmp_path):
    from research_pipeline.smells.filter import ruff_candidates

    (tmp_path / "m.py").write_text("x = 1\n\n\ndef f(a, b, c, d, e, g, h):\n    return a\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def g(:\n", encoding="utf-8")
    [candidate] = ruff_candidates(tmp_path)
    assert (candidate.smell, candidate.path, candidate.line, candidate.tool) == ("LongParameterList", "m.py", 4,
                                                                                "ruff:PLR0913")
    assert candidate.code.startswith("def f(") and candidate.first_line == 4
