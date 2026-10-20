import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "v2_self_consistency", Path(__file__).resolve().parents[1] / "scripts/v2_self_consistency.py")
v2_self_consistency = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2_self_consistency)

ITEMS = {"a": {"id": "a", "function": "f", "bug_lines": ["return 1 / x"]},
         "b": {"id": "b", "function": "g", "bug_lines": ["return y[0]"]}}


def _h(function, expression):
    return {"function": function, "suspect_expression": expression}


def test_votes_keep_hypotheses_seen_in_k_runs(monkeypatch):
    monkeypatch.setattr(v2_self_consistency, "at_bug_line",
                        lambda h, item: h["suspect_expression"] in " ".join(item["bug_lines"]))
    hit_a, hit_b, miss = ("a", "f", "1 / x"), ("b", "g", "y[0]"), ("a", "f", "x + 1")
    runs = [{hit_a: _h("f", "1 / x"), miss: _h("f", "x + 1")},
            {hit_a: _h("f", "1 / x"), hit_b: _h("g", "y[0]")},
            {miss: _h("f", "x + 1")}]
    assert v2_self_consistency.vote(runs, ITEMS, 1) == {"k": 1, "kept": 3, "bugs_at_line": 2, "precision": 2 / 3}
    assert v2_self_consistency.vote(runs, ITEMS, 2) == {"k": 2, "kept": 2, "bugs_at_line": 1, "precision": 0.5}
    assert v2_self_consistency.vote(runs, ITEMS, 3)["kept"] == 0
