import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from research_pipeline.scan import replay_worker
from research_pipeline.scan.replay import ReplayCase, ReplayOutcome
from research_pipeline.scan.witness import assess_witness
from research_pipeline.verification.esbmc_runner import (
    _extract_esbmc_details,
    run_esbmc_on_function,
)

SOURCE = "def f(x: int) -> int:\n    return 10 // x\n"


class _TrustedFixtureExecutor:
    """Exercise the real worker only on the literal test fixture, never user code."""

    def __init__(self, directory, source):
        self.directory = directory
        self.source = source

    def run(self, source, function, case):
        assert source == self.source
        candidate = self.directory / "candidate.py"
        result = self.directory / "result.json"
        candidate.write_text(source, encoding="utf-8")
        subprocess.run(
            [sys.executable, "-I", replay_worker.__file__, str(candidate), function,
             json.dumps(case.args), json.dumps(case.kwargs), str(result)],
            check=True, capture_output=True, text=True, timeout=5,
        )
        return ReplayOutcome(**json.loads(result.read_text(encoding="utf-8")))


def _trace(*, line=2, file="rewrite.py", assignments=None, kind="uncaught exception: ZeroDivisionError"):
    assignments = ["x = 0"] if assignments is None else assignments
    return (
        "[Counterexample]\n\n"
        f"State 1 file {file} line 1 column 0 thread 0\n"
        "----------------------------------------------------\n"
        + "".join(f"  {assignment}\n" for assignment in assignments)
        + f"\nState 2 file {file} line {line} column 11 function f thread 0\n"
        "----------------------------------------------------\n"
        "Violated property:\n"
        f"  file {file} line {line} column 11 function f\n"
        f"  {kind}\n"
        "  !(exception)\n\n"
    )


def _assess(tmp_path, *, source=SOURCE, trace=None, function="f", category="division_by_zero", original_line=2):
    details = _extract_esbmc_details(_trace() if trace is None else trace, Path("rewrite.py"))
    return assess_witness(
        details, expected_category=category, rewritten_file="rewrite.py",
        rewritten_line=2, original_source=source, function=function,
        original_line=original_line, original_column=11,
        executor=_TrustedFixtureExecutor(tmp_path, source),
    )


def test_exact_native_property_and_line_replays_on_original(tmp_path):
    assessment = _assess(tmp_path)
    assert assessment.status == "reproduced_original"
    assert assessment.case == ReplayCase((0,), {})


@pytest.mark.parametrize("trace", [_trace(line=3), _trace(file="other.py")])
def test_other_location_is_unattributed(tmp_path, trace):
    assert _assess(tmp_path, trace=trace).status == "unattributed"


def test_passed_typeerror_does_not_hide_zero_division(tmp_path):
    trace = "PASSED [f.1] TypeError: object has no len()\n" + _trace()
    assert _assess(tmp_path, trace=trace).status == "reproduced_original"


def test_incomplete_counterexample_is_rewrite_only(tmp_path):
    assessment = _assess(tmp_path, trace=_trace(assignments=[]))
    assert assessment.status == "rewrite_only"
    assert assessment.case is None


def test_concrete_counterexample_contradicts_original(tmp_path):
    assert _assess(tmp_path, source="def f(x):\n    return x\n").status == "contradicted"


def test_self_state_not_reconstructible_stays_rewrite_only(tmp_path):
    source = "class C:\n    def f(self, x):\n        return self.value // x\n"
    assessment = _assess(tmp_path, source=source, function="C.f")
    assert assessment.status == "rewrite_only"
    assert assessment.case is None


def test_wrong_category_is_unattributed(tmp_path):
    assert _assess(tmp_path, category="incorrect_result").status == "unattributed"


def test_pipeline_out_of_bounds_category_is_recognized(tmp_path):
    assessment = _assess(
        tmp_path, source="def f(x):\n    return [10][x]\n", category="out_of_bounds",
        trace=_trace(assignments=["x = 2"], kind="uncaught exception: IndexError"),
    )
    assert assessment.status == "reproduced_original"


def test_initialization_failure_never_confirms_target(tmp_path):
    assessment = _assess(tmp_path, source="value = 10 // 0\n\ndef f(x):\n    return x\n")
    assert assessment.status == "rewrite_only"


def test_same_exception_on_another_line_does_not_confirm(tmp_path):
    source = "def f(x):\n    y = x\n    return 10 // y\n"
    assert _assess(tmp_path, source=source).status == "contradicted"


def test_same_exception_on_another_column_does_not_confirm(tmp_path):
    source = "def f(x):\n    return (10 // x, 20 // x)\n"
    assert _assess(tmp_path, source=source).status == "contradicted"


def test_missing_original_location_is_not_confirmed(tmp_path):
    assert _assess(tmp_path, original_line=None).status == "unattributed"


def test_multiple_assignments_are_not_guessed(tmp_path):
    result = _assess(tmp_path, trace=_trace(assignments=["x = 1", "x = 0"]))
    assert result.status == "rewrite_only"


def test_counterexample_belongs_to_selected_property(tmp_path):
    trace = _trace(line=3, assignments=["x = 2"]) + _trace(assignments=["x = 0"])
    result = _assess(tmp_path, trace=trace)
    assert result.status == "reproduced_original"
    assert result.case == ReplayCase((0,), {})


def test_property_without_its_own_trace_does_not_reuse_previous_inputs(tmp_path):
    second = _trace(assignments=[]).replace("[Counterexample]\n\n", "")
    result = _assess(tmp_path, trace=_trace(line=3) + second)
    assert result.status == "rewrite_only"


def test_runner_preserves_full_property_trace_for_replay():
    details = _extract_esbmc_details(_trace(assignments=[f"arg{i} = {i}" for i in range(8)]))
    assert len(details["counterexample"]) == 6  # legacy display summary
    assert details["violated_property_records"][0]["counterexample"] == [f"arg{i} = {i}" for i in range(8)]


def test_runner_records_assignment_frames_and_property_position():
    record = _extract_esbmc_details(_trace(assignments=["x = 0"]))["violated_property_records"][0]
    assert record["line"] == 2 and record["column"] == 11
    assert record["assignments"] == [{"function": "", "line": 1, "name": "x", "value": "0"}]


DRIVER_SOURCE = "def main():\n    divisor: int = nondet_int()\n    f(divisor)\n\nmain()\n"


def _driver_trace(assignments=("divisor = 0",), function="main"):
    return (
        "[Counterexample]\n\n"
        f"State 1 file rewrite.py line 7 column 4 function {function} thread 0\n"
        "----------------------------------------------------\n"
        + "".join(f"  {assignment}\n" for assignment in assignments)
        + "\nState 2 file rewrite.py line 2 column 11 function f thread 0\n"
        "----------------------------------------------------\n"
        "Violated property:\n"
        "  file rewrite.py line 2 column 11 function f\n"
        "  uncaught exception: ZeroDivisionError\n"
        "  !(exception)\n\n"
    )


def _assess_driver(tmp_path, trace, *, driver=DRIVER_SOURCE, source=SOURCE, function="f"):
    return assess_witness(
        _extract_esbmc_details(trace, Path("rewrite.py")),
        expected_category="division_by_zero", rewritten_file="rewrite.py",
        rewritten_line=2, original_source=source, function=function,
        original_line=2, original_column=11, driver_source=driver,
        executor=_TrustedFixtureExecutor(tmp_path, source),
    )


def test_driver_local_names_map_to_entry_arguments(tmp_path):
    assessment = _assess_driver(tmp_path, _driver_trace())
    assert assessment.status == "reproduced_original"
    assert assessment.case == ReplayCase((0,), {})


def test_driver_literal_argument_is_replayed(tmp_path):
    driver = "def main():\n    f(0)\n\nmain()\n"
    assessment = _assess_driver(tmp_path, _driver_trace(assignments=()), driver=driver)
    assert assessment.status == "reproduced_original"
    assert assessment.case == ReplayCase((0,), {})


def test_callee_local_with_driver_name_is_not_used(tmp_path):
    assessment = _assess_driver(tmp_path, _driver_trace(function="f"))
    assert assessment.status == "rewrite_only"


def test_driver_argument_computed_from_nondet_is_not_guessed(tmp_path):
    driver = "def main():\n    divisor: int = nondet_int()\n    f(divisor + 1)\n\nmain()\n"
    assert _assess_driver(tmp_path, _driver_trace(), driver=driver).status == "rewrite_only"


def test_method_entry_at_suspect_line_is_rewrite_only(tmp_path):
    source = "class C:\n    def f(self, x):\n        return 10 // x\n"
    driver = "def main():\n    C().f(nondet_int())\n\nmain()\n"
    assessment = _assess_driver(tmp_path, _driver_trace(), driver=driver, source=source, function="C.f")
    assert assessment.status == "rewrite_only"
    assert "object" in assessment.reason


@pytest.mark.skipif(shutil.which("esbmc") is None, reason="ESBMC binary unavailable")
def test_real_esbmc_driver_counterexample_replays_on_original(tmp_path):
    rewritten = tmp_path / "rewrite.py"
    rewritten.write_text(SOURCE + "\n\n" + DRIVER_SOURCE, encoding="utf-8")
    from research_pipeline.verification.esbmc_runner import run_esbmc_direct
    result = run_esbmc_direct(rewritten, bound=3, timeout_seconds=15, output_dir=tmp_path / "logs")
    assert result.status == "violation_found", result.summary
    assessment = assess_witness(
        result.details, expected_category="division_by_zero", rewritten_file=str(rewritten),
        rewritten_line=2, original_source=SOURCE, function="f", original_line=2,
        original_column=11, driver_source=DRIVER_SOURCE,
        executor=_TrustedFixtureExecutor(tmp_path, SOURCE),
    )
    assert assessment.status == "reproduced_original", assessment.reason


@pytest.mark.skipif(shutil.which("esbmc") is None, reason="ESBMC binary unavailable")
def test_real_esbmc_counterexample_replays_on_original(tmp_path):
    original = tmp_path / "original.py"
    original.write_text(SOURCE, encoding="utf-8")
    result = run_esbmc_on_function(
        original, "f", "witness", "division_by_zero",
        bound=3, timeout_seconds=15, output_dir=tmp_path / "logs",
    )
    assert result.status == "violation_found", result.summary
    assessment = assess_witness(
        result.details, expected_category="division_by_zero", rewritten_file=str(original),
        rewritten_line=2, original_source=SOURCE, function="f", original_line=2,
        original_column=11, executor=_TrustedFixtureExecutor(tmp_path, SOURCE),
    )
    assert assessment.status == "reproduced_original"


def test_different_exception_type_on_original_is_unattributed(tmp_path):
    source = "def f(x):\n    return missing_name // x\n"
    assert _assess(tmp_path, source=source).status == "unattributed"


def test_suspect_inside_nested_scope_matches_by_position(tmp_path):
    source = "def f(x):\n    return (lambda: 10 // x)()\n"
    assessment = assess_witness(
        _extract_esbmc_details(_trace(), Path("rewrite.py")),
        expected_category="division_by_zero", rewritten_file="rewrite.py", rewritten_line=2,
        original_source=source, function="f", original_line=2, original_column=20,
        executor=_TrustedFixtureExecutor(tmp_path, source),
    )
    assert assessment.status == "reproduced_original", assessment.reason
