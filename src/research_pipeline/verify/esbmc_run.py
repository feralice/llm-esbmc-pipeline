"""One ESBMC check of a program, as both verification levels run it.

A reading that says only "the bound was short" (unwinding assertions) is retried with a larger
bound; a timeout is retried with other solvers. A later run replaces the reading only when it is
an ESBMC verdict, so a crash or timeout at a larger bound never discards a valid result. Each run
writes its log to its own directory, so the counterexample read later is that of the kept run.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Callable

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verification.esbmc_runner import run_esbmc_direct

from .outcome import EsbmcReading, classify_esbmc

VERDICT_KINDS = frozenset({"violation", "artifact", "safe"})
_UNBOUNDED = frozenset({"--incremental-bmc", "--k-induction"})
# Solvers differ per program: Boolector and Z3 finished some programs Bitwuzla did not (2026-09-30).
FALLBACK_SOLVERS = ("--boolector", "--z3")
_SOLVER_FLAGS = {"--boolector", "--z3", "--bitwuzla", "--cvc5", "--cvc4", "--yices", "--mathsat", "--smtlib"}

Runner = Callable[..., ESBMCDirectResult]
# ESBMC's string model loops once per character: a nondet string needs more unwinding than the program's
# own loops, and raising every loop to that bound is what timed out (fast_float, 2026-10-28).
LIBRARY_UNWIND = 64
# A run killed after printing the target exception gets one rerun this long: at 300 s the three GPS
# programs that timed out at 180 s reached a full verdict (RESULTADOS_MELHORIAS_PIPELINE_PGENE601_2026-11-03).
ESCALATED_TIMEOUT = 300
_LOOP = re.compile(r"goto-loop Loop \d+ \(([^():]+:\d+)\):\s*\n\s*file (\S+)")


def library_loops(show_loops: str, program: Path) -> list[str]:
    """``function:index`` of every loop ``--show-loops`` places outside ``program``."""
    return [loop for loop, file in _LOOP.findall(show_loops) if Path(file).name != Path(program).name]


def library_flags(how: dict) -> list[str]:
    """The flags that gave the library loops their own bound in the kept run; later runs of the same
    program (reachability probe, pytest generator) need them to reach the same depth."""
    loops = how.get("library_loops") or []
    return ["--unwindsetname", ",".join(f"{loop}:{how['library_unwind']}" for loop in loops)] if loops else []


def _only_library_unwinding(result: ESBMCDirectResult, program: Path) -> bool:
    files = result.details.get("violated_files") or []
    return bool(files) and all(file and Path(file).name != Path(program).name for file in files)


def only_unwinding(reading: EsbmcReading) -> bool:
    kinds = [kind.strip() for kind in reading.message.split(";")]
    return reading.kind == "artifact" and all(kind.startswith("unwinding assertion") for kind in kinds)


def _partial_exception_violation(result: ESBMCDirectResult, program: Path) -> EsbmcReading | None:
    """Read only a completed target-exception counterexample from a run later killed by timeout.

    The normal classifier requires ESBMC's final verdict. Here the solver may have printed a complete
    counterexample for one property before timing out on another, so replay is still mandatory.
    """
    output = esbmc_output(result)
    if result.status != "timeout" or "[Counterexample]" not in output or "Violated property:\n" not in output:
        return None
    records = result.details.get("violated_property_records") or []
    target_records = [record for record in records if isinstance(record, dict)
                      and Path(str(record.get("file", ""))).name == program.name
                      and re.match(r"uncaught exception: [A-Za-z_]\w*", str(record.get("kind", "")))]
    if not target_records:
        return None
    details = dict(result.details)
    details["violated_property_records"] = target_records
    details["violated_properties"] = list(dict.fromkeys(str(r["kind"]) for r in target_records))
    details["violated_files"] = [str(r["file"]) for r in target_records]
    partial = replace(result, status="violation_found", details=details)
    reading = classify_esbmc(partial)
    return reading if reading.kind == "violation" else None


def esbmc_output(result: ESBMCDirectResult) -> str:
    try:
        return Path(result.raw_log_path).read_text(encoding="utf-8", errors="replace") if result.raw_log_path else result.stdout
    except OSError:
        return result.stdout


def check(path: Path, *, esbmc_command: list[str] | None, bound: int, timeout_seconds: int, work_dir: Path,
          runner: Runner | None = None) -> tuple[ESBMCDirectResult, EsbmcReading, dict]:
    """Returns the kept run, its reading, and how it was obtained ({"unwind": n, "solver": flag})."""
    runner = runner or run_esbmc_direct
    library: list[str] = []
    partial_timeout: tuple[ESBMCDirectResult, EsbmcReading, str] | None = None

    def run(unwind: int, solver: str = "", tag_suffix: str = "",
            seconds: int = timeout_seconds) -> tuple[ESBMCDirectResult, EsbmcReading]:
        tag = f"esbmc_unwind{unwind}{solver.replace('--', '_')}{tag_suffix}"
        unbounded = solver in _UNBOUNDED
        bound_flags = [] if unbounded else ["--unwind", str(unwind)]
        extra = [solver] if solver else []
        # Incremental BMC and k-induction raise every loop themselves; a fixed library bound would cap them.
        if library and not unbounded:
            extra += ["--unwindsetname", ",".join(f"{loop}:{LIBRARY_UNWIND}" for loop in library)]
        result = runner(path, esbmc_command=esbmc_command, bound=unwind, timeout_seconds=seconds,
                        output_dir=Path(work_dir) / tag, bound_flags=bound_flags, extra_flags=extra or None)
        return result, classify_esbmc(result)

    esbmc, reading = run(bound)
    partial = _partial_exception_violation(esbmc, path)
    if partial is not None:
        partial_timeout = (esbmc, partial, "")
    how: dict = {"unwind": bound}
    if only_unwinding(reading) and _only_library_unwinding(esbmc, path):
        listing = runner(path, esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                         output_dir=Path(work_dir) / "esbmc_show_loops", bound_flags=[], extra_flags=["--show-loops"])
        library = library_loops(esbmc_output(listing), path)
        if library:
            result, result_reading = run(bound, tag_suffix="_library")
            partial = _partial_exception_violation(result, path)
            if partial is not None:
                partial_timeout = (result, partial, "")
            if result_reading.kind in VERDICT_KINDS:
                esbmc, reading, how = result, result_reading, {"unwind": bound, "library_unwind": LIBRARY_UNWIND,
                                                                "library_loops": library}
            else:
                library = []
    for unwind in (bound * 2, bound * 4):
        if not only_unwinding(reading):
            break
        result, result_reading = run(unwind)
        partial = _partial_exception_violation(result, path)
        if partial is not None:
            partial_timeout = (result, partial, "")
        if result_reading.kind not in VERDICT_KINDS:
            break
        esbmc, reading, how = result, result_reading, {**how, "unwind": unwind}
    if only_unwinding(reading) and how["unwind"] == bound * 4:
        # Still short at 4x: let ESBMC raise the bound itself, as the ESBMC plugin does for loops of unknown bound.
        result, result_reading = run(0, "--incremental-bmc")
        if result_reading.kind in VERDICT_KINDS and not only_unwinding(result_reading):
            esbmc, reading, how = result, result_reading, {**how, "unwind": "incremental"}
        else:
            # The inductive step can prove safety where no bound reaches every iteration; UNKNOWN keeps the bound.
            result, result_reading = run(0, "--k-induction")
            if result_reading.kind in VERDICT_KINDS and not only_unwinding(result_reading):
                esbmc, reading, how = result, result_reading, {**how, "unwind": "k-induction"}
    if reading.kind == "timeout" and not _SOLVER_FLAGS.intersection(esbmc_command or []):
        for solver in FALLBACK_SOLVERS:
            result, result_reading = run(how["unwind"], solver)
            partial = _partial_exception_violation(result, path)
            if partial is not None:
                partial_timeout = (result, partial, solver)
            if result_reading.kind in VERDICT_KINDS:
                esbmc, reading, how = result, result_reading, {**how, "solver": solver}
                break
    if reading.kind == "timeout" and partial_timeout is not None and timeout_seconds < ESCALATED_TIMEOUT \
            and isinstance(how["unwind"], int):
        # Only here, never as the global bound: the exception is already in the log, the rest is the solver.
        result, result_reading = run(how["unwind"], partial_timeout[2], f"_{ESCALATED_TIMEOUT}s", ESCALATED_TIMEOUT)
        if result_reading.kind in VERDICT_KINDS:
            esbmc, reading = result, result_reading
            how = {**how, "timeout_escalated": ESCALATED_TIMEOUT,
                   **({"solver": partial_timeout[2]} if partial_timeout[2] else {})}
        else:
            partial = _partial_exception_violation(result, path)
            if partial is not None:
                partial_timeout = (result, partial, partial_timeout[2])
    if reading.kind == "timeout" and partial_timeout is not None:
        esbmc, partial_reading, solver = partial_timeout
        reading = partial_reading
        how = {**how, "partial_timeout": True, "partial_solver": solver or "default",
               "partial_log": esbmc.raw_log_path}
    return esbmc, reading, how
