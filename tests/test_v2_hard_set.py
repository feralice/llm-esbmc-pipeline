import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "v2_hard_set", Path(__file__).resolve().parents[1] / "scripts" / "v2_hard_set.py")
v2_hard_set = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v2_hard_set)

GROUND_TRUTH = {
    "a": {"function": "f", "expression": "x[i]", "crash_expressions": []},
    "b": {"function": "g / h", "expression": "1 // n", "crash_expressions": ["y.k"]},
    "c": {"function": "f", "expression": "z + 1", "crash_expressions": []},
    "d": {"function": "f", "expression": "", "crash_expressions": []},
}


def _result(hid: str, stem: str, function: str, expression: str, verdict: str) -> dict:
    return {"verdict": verdict, "hypothesis": {"hypothesis_id": hid, "file": f"x/{stem}.py",
                                                "function": function, "suspect_expression": expression}}


def test_only_hypotheses_at_a_labelled_bug_line_are_picked() -> None:
    results = [_result("1", "a", "f", "x[i]", "UNSUPPORTED"),
               _result("2", "a", "f", "other()", "UNSUPPORTED"),
               _result("3", "b", "h", "y.k", "MISSING_DEPENDENCY"),
               _result("4", "c", "other", "z + 1", "UNSUPPORTED"),
               _result("5", "d", "f", "anything", "UNSUPPORTED")]
    assert {c["hypothesis_id"] for c in v2_hard_set.hard_set(results, GROUND_TRUTH, size=10)} == {"1", "3"}


def test_esbmc_verdicts_are_kept_and_stuck_classes_alternate() -> None:
    results = [_result("u1", "a", "f", "x[i]", "UNSUPPORTED"),
               _result("u2", "c", "f", "z + 1", "UNSUPPORTED"),
               _result("m1", "b", "g", "1 // n", "MISSING_DEPENDENCY"),
               _result("ok", "a", "f", "x[i]", "CONFIRMED")]
    picked = v2_hard_set.hard_set(results, GROUND_TRUTH, size=3)
    assert [c["hypothesis_id"] for c in picked] == ["ok", "m1", "u1"]


def test_a_repeated_hypothesis_counts_once() -> None:
    results = [_result("1", "a", "f", "x[i]", "UNSUPPORTED"), _result("1", "a", "f", "x[i]", "UNSUPPORTED")]
    assert len(v2_hard_set.hard_set(results, GROUND_TRUTH, size=10)) == 1
