from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify.esbmc_run import check

UNWIND = ("violation_found", ["unwinding assertion loop 3"])
BUG = ("violation_found", ["uncaught exception: ZeroDivisionError"])
TIMEOUT = ("timeout", [])
CRASH = ("tool_error", [])


def _runner(*outcomes):
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        status, kinds = outcomes[len(calls)]
        calls.append({"bound": bound, "solver": (extra_flags or [""])[0], "dir": Path(output_dir).name})
        return ESBMCDirectResult(source_file=str(path), status=status, command=["esbmc"], returncode=1,
                                 summary=status, details={"violated_properties": kinds,
                                                          "violated_files": ["p.py"] * len(kinds)})
    run.calls = calls
    return run


@pytest.mark.parametrize(("outcomes", "kept", "how"), [
    ((BUG,), "uncaught exception: ZeroDivisionError", {"unwind": 5}),
    ((UNWIND, BUG), "uncaught exception: ZeroDivisionError", {"unwind": 10}),
    ((UNWIND, UNWIND, BUG), "uncaught exception: ZeroDivisionError", {"unwind": 20}),
    ((UNWIND, UNWIND, UNWIND, BUG), "uncaught exception: ZeroDivisionError", {"unwind": "incremental"}),
    ((UNWIND, UNWIND, UNWIND, UNWIND), "unwinding assertion loop 3", {"unwind": 20}),
    # A larger bound that crashes or times out leaves the valid reading of the smaller one standing.
    ((UNWIND, CRASH), "unwinding assertion loop 3", {"unwind": 5}),
    ((UNWIND, TIMEOUT), "unwinding assertion loop 3", {"unwind": 5}),
    ((TIMEOUT, BUG), "uncaught exception: ZeroDivisionError", {"unwind": 5, "solver": "--boolector"}),
    ((TIMEOUT, CRASH, BUG), "uncaught exception: ZeroDivisionError", {"unwind": 5, "solver": "--z3"}),
])
def test_check_keeps_the_best_reading(tmp_path, outcomes, kept, how):
    runner = _runner(*outcomes)
    _, reading, got = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                            work_dir=tmp_path, runner=runner)
    assert (reading.message, got) == (kept, how)
    assert len(runner.calls) == len(outcomes)
    assert len({call["dir"] for call in runner.calls}) == len(outcomes)


def test_no_solver_fallback_when_the_command_already_picks_one(tmp_path):
    runner = _runner(TIMEOUT)
    _, reading, _ = check(tmp_path / "p.py", esbmc_command=["esbmc", "--z3"], bound=5, timeout_seconds=1,
                          work_dir=tmp_path, runner=runner)
    assert reading.kind == "timeout" and len(runner.calls) == 1
