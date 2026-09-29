import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify.outcome import (
    CONFIRMED,
    ESBMC_ERROR,
    ESBMC_MISSED,
    ESBMC_TIMEOUT,
    MISSING_DEPENDENCY,
    NOT_CONFIRMED,
    OTHER_FAILURE,
    UNSUPPORTED,
    UNVALIDATED,
    EsbmcReading,
    classify_esbmc,
    final_verdict,
)
from research_pipeline.verify.replay import ReplayVerdict


def _result(status, *, kinds=(), files=(), stdout="", summary=""):
    return ESBMCDirectResult(
        source_file="p.py", status=status, command=["esbmc"], returncode=1, summary=summary,
        stdout=stdout, details={"violated_properties": list(kinds), "violated_files": list(files)},
    )


def test_real_violation():
    reading = classify_esbmc(_result("violation_found", kinds=["uncaught exception: ZeroDivisionError"], files=[""]))
    assert reading.kind == "violation"


def test_unwinding_only_is_not_a_violation():
    reading = classify_esbmc(_result("violation_found", kinds=["unwinding assertion loop 3"], files=["x.c"]))
    assert reading.kind == "artifact"


@pytest.mark.parametrize("status", ["no_violation_found", "no_vcc_generated"])
def test_no_counterexample_statuses_are_safe(status):
    assert classify_esbmc(_result(status)).kind == "safe"


def test_timeout():
    assert classify_esbmc(_result("timeout", summary="excedeu o tempo")).kind == "timeout"


def test_missing_module_is_a_dependency_problem():
    reading = classify_esbmc(_result("unsupported_case", stdout="ERROR: Cannot open file: thefuck/utils.py"))
    assert reading.kind == "missing_dependency"


def test_other_conversion_error_is_repairable_with_message():
    reading = classify_esbmc(_result("tool_error", stdout="ERROR: Type inference failed for xs"))
    assert reading.kind == "repairable"
    assert "Type inference failed" in reading.message


def test_esbmc_not_found_is_an_error():
    assert classify_esbmc(_result("skipped")).kind == "error"


R = ReplayVerdict


@pytest.mark.parametrize(
    ("reading", "replay", "verdict"),
    [
        ("violation", R("reproduced", "ZeroDivisionError"), CONFIRMED),
        ("violation", R("other_failure"), OTHER_FAILURE),
        ("violation", R("not_reproduced"), UNVALIDATED),
        ("violation", R("unavailable"), UNVALIDATED),
        ("safe", R("reproduced", "ZeroDivisionError"), ESBMC_MISSED),
        ("safe", R("not_reproduced"), NOT_CONFIRMED),
        ("safe", R("other_failure"), NOT_CONFIRMED),
        ("artifact", R("reproduced", "ZeroDivisionError"), ESBMC_MISSED),
        ("artifact", R("not_reproduced"), NOT_CONFIRMED),
        ("timeout", R("not_reproduced"), ESBMC_TIMEOUT),
        ("missing_dependency", R("unavailable"), MISSING_DEPENDENCY),
        ("repairable", R("unavailable"), UNSUPPORTED),
        ("error", R("unavailable"), ESBMC_ERROR),
    ],
)
def test_final_verdict_table(reading, replay, verdict):
    assert final_verdict(EsbmcReading(reading, "", frozenset({"ZeroDivisionError"})), replay) == verdict
