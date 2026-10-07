import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "v2_orchestrate", Path(__file__).resolve().parents[1] / "scripts" / "v2_orchestrate.py")
v2_orchestrate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v2_orchestrate)

GT = {"a": {"function": "f", "expression": "x[i]", "crash_expressions": []}}


def _result(hid, expression):
    return {"hypothesis": {"hypothesis_id": hid, "file": "d/a.py", "function": "f", "suspect_expression": expression}}


def test_summary_counts_formal_and_dynamic_findings_at_the_bug_line_apart() -> None:
    results = [_result("1", "x[i]"), _result("2", "x[i]"), _result("3", "y")]
    rows = [{"hypothesis_id": "1", "final": "CONFIRMED", "steps": []},
            {"hypothesis_id": "2", "final": "FUZZ_FOUND", "steps": []},
            {"hypothesis_id": "3", "final": "CONFIRMED", "steps": []}]
    summary = v2_orchestrate.summarize(rows, results, GT)
    assert summary["confirmed_at_bug"] == 1 and summary["fuzz_found_at_bug"] == 1
    assert summary["final"] == {"CONFIRMED": 2, "FUZZ_FOUND": 1}


def test_a_dynamic_finding_counts_only_when_the_fixed_version_does_not_crash_too() -> None:
    results = [_result(h, "x[i]") for h in ("1", "2", "3")]
    rows = [{"hypothesis_id": h, "final": "FUZZ_FOUND", "steps": []} for h in ("1", "2", "3")]
    control = [{"hypothesis_id": "1", "final": "FUZZ_FOUND"}, {"hypothesis_id": "2", "final": "FUZZ_NOTHING"},
               {"hypothesis_id": "3", "final": "FUZZ_UNAVAILABLE"}]
    summary = v2_orchestrate.summarize(rows, results, GT, control=control)
    assert summary["fuzz_found_at_bug"] == 3
    assert summary["fuzz_found_at_bug_not_on_fixed"] == 2 and summary["fuzz_found_at_bug_fixed_ran_clean"] == 1


def test_an_agent_verdict_on_a_rewritten_function_is_not_formal() -> None:
    assert v2_orchestrate.agent_outcome({"verdict": "NOT_CONFIRMED", "target_preserved": False})["verdict"] == \
        "TARGET_ALTERED"
    assert v2_orchestrate.agent_outcome({"verdict": "CONFIRMED", "target_preserved": True})["verdict"] == "CONFIRMED"
