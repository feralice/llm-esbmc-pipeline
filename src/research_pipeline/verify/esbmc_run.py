"""One ESBMC check of a program, as both verification levels run it.

A reading that says only "the bound was short" (unwinding assertions) is retried with a larger
bound; a timeout is retried with other solvers. A later run replaces the reading only when it is
an ESBMC verdict, so a crash or timeout at a larger bound never discards a valid result. Each run
writes its log to its own directory, so the counterexample read later is that of the kept run.
"""

from __future__ import annotations

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
    def run(unwind: int, solver: str = "") -> tuple[ESBMCDirectResult, EsbmcReading]:
        tag = f"esbmc_unwind{unwind}{solver.replace('--', '_')}"
        bound_flags = [] if solver == "--incremental-bmc" else ["--unwind", str(unwind)]
        result = runner(path, esbmc_command=esbmc_command, bound=unwind, timeout_seconds=timeout_seconds,
                        output_dir=Path(work_dir) / tag, bound_flags=bound_flags,
                        extra_flags=[solver] if solver else None)
        return result, classify_esbmc(result)

    esbmc, reading = run(bound)
    how = {"unwind": bound}
    for unwind in (bound * 2, bound * 4):
        if not only_unwinding(reading):
            break
        result, result_reading = run(unwind)
        if result_reading.kind not in VERDICT_KINDS:
            break
        esbmc, reading, how = result, result_reading, {"unwind": unwind}
    if only_unwinding(reading) and how["unwind"] == bound * 4:
        # Still short at 4x: let ESBMC raise the bound itself, as the ESBMC plugin does for loops of unknown bound.
        result, result_reading = run(0, "--incremental-bmc")
        if result_reading.kind in VERDICT_KINDS and not only_unwinding(result_reading):
            esbmc, reading, how = result, result_reading, {"unwind": "incremental"}
    if reading.kind == "timeout" and not _SOLVER_FLAGS.intersection(esbmc_command or []):
        for solver in FALLBACK_SOLVERS:
            result, result_reading = run(how["unwind"], solver)
            if result_reading.kind in VERDICT_KINDS:
                esbmc, reading, how = result, result_reading, {**how, "solver": solver}
                break
    return esbmc, reading, how
