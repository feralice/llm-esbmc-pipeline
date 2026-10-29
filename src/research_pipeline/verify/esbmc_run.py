"""One ESBMC check of a program, as both verification levels run it.

A reading that says only "the bound was short" (unwinding assertions) is retried with a larger
bound; a timeout is retried with other solvers. A later run replaces the reading only when it is
an ESBMC verdict, so a crash or timeout at a larger bound never discards a valid result. Each run
writes its log to its own directory, so the counterexample read later is that of the kept run.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verification.esbmc_runner import run_esbmc_direct

from .outcome import EsbmcReading, classify_esbmc

VERDICT_KINDS = frozenset({"violation", "artifact", "safe"})
# Solvers differ per program: Boolector and Z3 finished some programs Bitwuzla did not (2026-09-30).
FALLBACK_SOLVERS = ("--boolector", "--z3")
_SOLVER_FLAGS = {"--boolector", "--z3", "--bitwuzla", "--cvc5", "--cvc4", "--yices", "--mathsat", "--smtlib"}

Runner = Callable[..., ESBMCDirectResult]
# ESBMC's string model loops once per character: a nondet string needs more unwinding than the program's
# own loops, and raising every loop to that bound is what timed out (fast_float, 2026-10-28).
LIBRARY_UNWIND = 64
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

    def run(unwind: int, solver: str = "", tag_suffix: str = "") -> tuple[ESBMCDirectResult, EsbmcReading]:
        tag = f"esbmc_unwind{unwind}{solver.replace('--', '_')}{tag_suffix}"
        bound_flags = [] if solver == "--incremental-bmc" else ["--unwind", str(unwind)]
        extra = [solver] if solver else []
        # Incremental BMC raises every loop itself; a fixed library bound would cap it.
        if library and solver != "--incremental-bmc":
            extra += ["--unwindsetname", ",".join(f"{loop}:{LIBRARY_UNWIND}" for loop in library)]
        result = runner(path, esbmc_command=esbmc_command, bound=unwind, timeout_seconds=timeout_seconds,
                        output_dir=Path(work_dir) / tag, bound_flags=bound_flags, extra_flags=extra or None)
        return result, classify_esbmc(result)

    esbmc, reading = run(bound)
    how: dict = {"unwind": bound}
    if only_unwinding(reading) and _only_library_unwinding(esbmc, path):
        listing = runner(path, esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                         output_dir=Path(work_dir) / "esbmc_show_loops", bound_flags=[], extra_flags=["--show-loops"])
        library = library_loops(esbmc_output(listing), path)
        if library:
            result, result_reading = run(bound, tag_suffix="_library")
            if result_reading.kind in VERDICT_KINDS:
                esbmc, reading, how = result, result_reading, {"unwind": bound, "library_unwind": LIBRARY_UNWIND,
                                                                "library_loops": library}
            else:
                library = []
    for unwind in (bound * 2, bound * 4):
        if not only_unwinding(reading):
            break
        result, result_reading = run(unwind)
        if result_reading.kind not in VERDICT_KINDS:
            break
        esbmc, reading, how = result, result_reading, {**how, "unwind": unwind}
    if only_unwinding(reading) and how["unwind"] == bound * 4:
        # Still short at 4x: let ESBMC raise the bound itself, as the ESBMC plugin does for loops of unknown bound.
        result, result_reading = run(0, "--incremental-bmc")
        if result_reading.kind in VERDICT_KINDS and not only_unwinding(result_reading):
            esbmc, reading, how = result, result_reading, {**how, "unwind": "incremental"}
    if reading.kind == "timeout" and not _SOLVER_FLAGS.intersection(esbmc_command or []):
        for solver in FALLBACK_SOLVERS:
            result, result_reading = run(how["unwind"], solver)
            if result_reading.kind in VERDICT_KINDS:
                esbmc, reading, how = result, result_reading, {**how, "solver": solver}
                break
    return esbmc, reading, how
