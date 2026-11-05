from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify.esbmc_run import ESCALATED_TIMEOUT, check

UNWIND = ("violation_found", ["unwinding assertion loop 3"])
BUG = ("violation_found", ["uncaught exception: ZeroDivisionError"])
TIMEOUT = ("timeout", [])
CRASH = ("tool_error", [])
SAFE = ("no_violation_found", [])
UNKNOWN = ("inconclusive", [])


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
    # Incremental BMC still short: k-induction may prove the program safe or find the bug; UNKNOWN keeps the bound.
    ((UNWIND, UNWIND, UNWIND, UNWIND, UNKNOWN), "unwinding assertion loop 3", {"unwind": 20}),
    ((UNWIND, UNWIND, UNWIND, UNWIND, SAFE), "no_violation_found", {"unwind": "k-induction"}),
    ((UNWIND, UNWIND, UNWIND, UNWIND, BUG), "uncaught exception: ZeroDivisionError", {"unwind": "k-induction"}),
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


SHOW_LOOPS = """goto-loop Loop 1 (__python_str_concat:0):
 file /home/fernanda/esbmc-master/src/c2goto/library/python/string.c line 1568 column 3 function __python_str_concat
goto-loop Loop 2 (main:0):
 file p.py line 7 column 4 function main
goto-loop Loop 3 (strlen:0):
 file /esbmc-vfs/libc/library/string.c line 93 column 3 function strlen
"""


def test_library_loops_parses_show_loops():
    from research_pipeline.verify.esbmc_run import library_loops
    assert library_loops(SHOW_LOOPS, Path("/tmp/x/p.py")) == ["__python_str_concat:0", "strlen:0"]


def test_unwinding_only_in_library_raises_only_library_loops(tmp_path):
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        calls.append({"bound": bound, "flags": list(extra_flags or [])})
        if "--show-loops" in calls[-1]["flags"]:
            return ESBMCDirectResult(source_file=str(path), status="tool_error", command=["esbmc"], returncode=0,
                                     summary="", stdout=SHOW_LOOPS)
        kinds, files = ((["unwinding assertion loop 3"], ["/esbmc-vfs/libc/library/string.c"]) if len(calls) == 1
                        else (["uncaught exception: ZeroDivisionError"], ["p.py"]))
        return ESBMCDirectResult(source_file=str(path), status="violation_found", command=["esbmc"], returncode=1,
                                 summary="", details={"violated_properties": kinds, "violated_files": files})

    _, reading, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                            work_dir=tmp_path, runner=run)
    assert reading.kind == "violation"
    assert how == {"unwind": 5, "library_unwind": 64, "library_loops": ["__python_str_concat:0", "strlen:0"]}
    assert calls[-1]["bound"] == 5
    assert calls[-1]["flags"] == ["--unwindsetname", "__python_str_concat:0:64,strlen:0:64"]


def test_unwinding_in_the_program_keeps_the_global_escalation(tmp_path):
    runner = _runner(UNWIND, BUG)
    _, _, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                      work_dir=tmp_path, runner=runner)
    assert how == {"unwind": 10}
    assert all(call["solver"] != "--show-loops" for call in runner.calls)


def test_library_flags_travel_in_how_but_not_into_incremental_bmc(tmp_path):
    from research_pipeline.verify.esbmc_run import library_flags
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        calls.append(list(extra_flags or []))
        if "--show-loops" in calls[-1]:
            return ESBMCDirectResult(source_file=str(path), status="tool_error", command=["esbmc"], returncode=0,
                                     summary="", stdout=SHOW_LOOPS)
        files = ["/esbmc-vfs/libc/library/string.c"] if len(calls) == 1 else ["p.py"]
        return ESBMCDirectResult(source_file=str(path), status="violation_found", command=["esbmc"], returncode=1,
                                 summary="", details={"violated_properties": ["unwinding assertion loop 3"],
                                                      "violated_files": files})

    _, _, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                      work_dir=tmp_path, runner=run)
    assert library_flags(how) == ["--unwindsetname", "__python_str_concat:0:64,strlen:0:64"]
    incremental = [flags for flags in calls if "--incremental-bmc" in flags]
    assert incremental and all("--unwindsetname" not in flags for flags in incremental)


def test_k_induction_runs_without_a_fixed_bound(tmp_path):
    flags = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        flags.append((list(bound_flags), list(extra_flags or [])))
        status, kinds = SAFE if "--k-induction" in (extra_flags or []) else UNWIND
        return ESBMCDirectResult(source_file=str(path), status=status, command=["esbmc"], returncode=0,
                                 summary=status, details={"violated_properties": kinds,
                                                          "violated_files": ["p.py"] * len(kinds)})

    check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1, work_dir=tmp_path, runner=run)
    assert flags[-1] == ([], ["--k-induction"])


PARTIAL_LOG = "[Counterexample]\nState 1 file p.py line 2\n\nViolated property:\n  file p.py line 2\n"


def _partial_timeout_runner(record_file):
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        calls.append((extra_flags or [""])[0])
        run.timeouts.append(timeout_seconds)
        record = {"kind": "uncaught exception: ZeroDivisionError", "file": record_file}
        return ESBMCDirectResult(source_file=str(path), status="timeout", command=["esbmc"], returncode=None,
                                 summary="timeout", stdout=PARTIAL_LOG,
                                 details={"violated_property_records": [record]})
    run.calls, run.timeouts = calls, []
    return run


def test_timeout_with_a_target_counterexample_is_read_as_a_partial_violation(tmp_path):
    runner = _partial_timeout_runner("p.py")
    _, reading, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                            work_dir=tmp_path, runner=runner)
    assert reading.kind == "violation" and reading.exceptions == {"ZeroDivisionError"}
    assert how["partial_timeout"] is True
    # The fallback solvers still run first: a full verdict always beats a partial one. Then one rerun
    # at ESCALATED_TIMEOUT with the solver that printed the counterexample last.
    assert runner.calls == ["", "--boolector", "--z3", "--z3"]
    assert runner.timeouts == [1, 1, 1, ESCALATED_TIMEOUT]
    assert "timeout_escalated" not in how


def test_a_partial_counterexample_earns_one_longer_run_that_can_finish(tmp_path):
    partial = _partial_timeout_runner("p.py")
    full = _runner(BUG)

    def run(path, **kwargs):
        return full(path, **kwargs) if kwargs["timeout_seconds"] == ESCALATED_TIMEOUT else partial(path, **kwargs)

    esbmc, reading, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=180,
                                work_dir=tmp_path, runner=run)
    assert reading.kind == "violation" and esbmc.status == "violation_found"
    assert how == {"unwind": 5, "timeout_escalated": ESCALATED_TIMEOUT, "solver": "--z3"}


@pytest.mark.parametrize("seconds", [ESCALATED_TIMEOUT, 900])
def test_no_escalation_at_or_above_the_escalated_timeout(tmp_path, seconds):
    runner = _partial_timeout_runner("p.py")
    check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=seconds, work_dir=tmp_path,
          runner=runner)
    assert runner.timeouts == [seconds] * 3


def test_a_plain_timeout_is_not_escalated(tmp_path):
    runner = _runner(TIMEOUT, TIMEOUT, TIMEOUT)
    _, reading, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=180,
                            work_dir=tmp_path, runner=runner)
    assert reading.kind == "timeout" and len(runner.calls) == 3 and "timeout_escalated" not in how


def test_partial_counterexample_outside_the_program_stays_a_timeout(tmp_path):
    _, reading, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                            work_dir=tmp_path, runner=_partial_timeout_runner("python_models.py"))
    assert reading.kind == "timeout" and "partial_timeout" not in how


def test_full_verdict_from_a_fallback_solver_beats_a_partial_one(tmp_path):
    partial = _partial_timeout_runner("p.py")
    full = _runner(BUG)

    def run(path, **kwargs):
        return partial(path, **kwargs) if not kwargs["extra_flags"] else full(path, **kwargs)

    _, reading, how = check(tmp_path / "p.py", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                            work_dir=tmp_path, runner=run)
    assert reading.kind == "violation" and how == {"unwind": 5, "solver": "--boolector"}
