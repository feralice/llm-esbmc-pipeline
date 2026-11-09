from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import compare_runs as cmp


def _report(verdicts: dict[tuple[str, str, str], str]) -> dict:
    return {"results": [{"hypothesis": {"file": f, "function": fn, "suspect_expression": e}, "verdict": v,
                         "seconds": 10.0} for (f, fn, e), v in verdicts.items()]}


def test_changes_lists_only_hypotheses_whose_verdict_differs() -> None:
    old = _report({("a.py", "f", "x"): "UNSUPPORTED", ("a.py", "f", "y"): "CONFIRMED", ("a.py", "g", "z"): "LLM_ONLY"})
    new = _report({("a.py", "f", "x"): "CONFIRMED", ("a.py", "f", "y"): "CONFIRMED", ("a.py", "g", "w"): "LLM_ONLY"})
    changes, only_old, only_new = cmp.changes(old, new)
    assert changes == [(("a.py", "f", "x"), "UNSUPPORTED", "CONFIRMED")]
    assert only_old == [("a.py", "g", "z")] and only_new == [("a.py", "g", "w")]


def test_counts_and_seconds_by_verdict() -> None:
    report = _report({("a.py", "f", "x"): "CONFIRMED", ("a.py", "f", "y"): "CONFIRMED", ("a.py", "g", "z"): "LLM_ONLY"})
    assert cmp.counts(report) == {"CONFIRMED": 2, "LLM_ONLY": 1}
    assert cmp.total_seconds(report) == 30.0
