"""Pipeline executors for the three experimental flows.

src/main.py parses CLI arguments and chooses the mode.
This module only executes the selected flow:

Flow A: ESBMC-only. It discovers functions and runs ESBMC on each one.
Flow B: Hybrid. The LLM proposes findings; ESBMC checks verifiable bugs.
Flow C: LLM-only. The LLM findings are kept without formal confirmation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .llm.backends.factory import Backend, build_analyzer  # noqa: F401 - re-exported
from .models import ESBMCDirectResult, ESBMCResult, FinalResult, Finding
from .preprocess import preprocess_file
from .report import consolidate_result, write_json_report
from .verification.esbmc_runner import (
    run_esbmc_direct,
    run_esbmc_function_baseline,
    run_esbmc_on_function,
)


# ---------------------------------------------------------------------------
# Flow A: ESBMC-only
# ---------------------------------------------------------------------------

def run_pipeline_esbmc_direct(
    input_paths: Sequence[str | Path],
    output_dir: str | Path = "artifacts/esbmc-direct",
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
) -> list[ESBMCDirectResult]:
    """Flow A: run ESBMC on every discovered function, without using an LLM.

    Input files are first preprocessed only to collect function names. Those names
    are then passed to ESBMC with --function. No prompt is built and no LLM is
    called in this flow.
    """
    results: list[ESBMCDirectResult] = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    num_files = len(input_paths)
    for i, input_path in enumerate(input_paths, 1):
        file_path = Path(input_path)
        print(f"[{i}/{num_files}] Verificando {file_path.name} (ESBMC-only)...")

        # Preprocessing is used here only to discover function names.
        units = preprocess_file(file_path)
        result = run_esbmc_function_baseline(
            file_path=file_path,
            function_names=[unit.name for unit in units],
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
        )
        results.append(result)

    summary_path = Path(output_dir) / "esbmc_direct_results.json"
    _write_json_atomic(summary_path, [result.to_dict() for result in results])
    return results


# ---------------------------------------------------------------------------
# Flow B: Hybrid, LLM + ESBMC
# ---------------------------------------------------------------------------

def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path = "artifacts/research-pipeline",
    esbmc_command: list[str] | None = None,
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    google_api_key: str | None = None,
    ollama_base_url: str | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    harness_for: dict[str, Path] | None = None,
    resume: bool = False,
) -> list[FinalResult]:
    """Flow B: convenience wrapper for analyzing one file.

    The real implementation is run_pipeline_multi(); this helper keeps tests and
    callers simple when they only have one input file.
    """
    return run_pipeline_multi(
        input_paths=[input_path],
        output_dir=output_dir,
        esbmc_command=esbmc_command,
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        google_api_key=google_api_key,
        ollama_base_url=ollama_base_url,
        bound=bound,
        timeout_seconds=timeout_seconds,
        harness_for=harness_for,
        resume=resume,
    )


def run_pipeline_multi(
    input_paths: Sequence[str | Path],
    output_dir: str | Path = "artifacts/research-pipeline",
    esbmc_command: list[str] | None = None,
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    google_api_key: str | None = None,
    ollama_base_url: str | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
    llm_timeout_seconds: int = 300,
    harness_for: dict[str, Path] | None = None,
    resume: bool = False,
) -> list[FinalResult]:
    """Flow B: LLM proposes findings; ESBMC checks verifiable bug findings.

    For each Python function:
    1. preprocess_file() creates a CodeUnit.
    2. analyzer.analyze() sends that CodeUnit to the LLM.
    3. Verifiable bug findings are checked with ESBMC.
    4. report.consolidate_result() turns each finding into a FinalResult.

    The pipeline keeps file_path internally so ESBMC can run on the real file.
    The prompt builder intentionally omits the path and pre-extracted operations
    from the LLM prompt to avoid dataset-category leakage.

    harness_for: optional {input_file_path_str: harness_file_path} map. When an
    input file has an entry here (dataset/v2_real_world/manifest_pilot.json
    already provides this mapping — detection_file -> harness_file), ESBMC
    verifies the mapped harness file directly (whole-file, no --function),
    not the file the LLM read. This is what keeps the harness's own oracle
    (nondet_*/asserts/precondition) hidden from the detection prompt while
    still letting a verifiable finding be checked formally: the LLM never
    sees the harness, and its file is unrelated in shape (often a different
    function name or a buggy/fixed pair), so --function on it would not make
    sense. Files with no entry keep the V1 behavior (run_esbmc_on_function on
    the same file, via --function).
    """
    analyzer = build_analyzer(
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        google_api_key=google_api_key,
        ollama_base_url=ollama_base_url,
        timeout_seconds=llm_timeout_seconds,
    )
    artifacts_dir = Path(output_dir)
    fingerprint = _run_fingerprint(
        mode="hybrid", backend=backend, model=getattr(analyzer, "model", llm_model),
        bound=bound, timeout=timeout_seconds,
        llm_timeout=llm_timeout_seconds, esbmc_command=esbmc_command,
        harness_for=harness_for,
    )
    results, completed_units = _initialize_run(artifacts_dir, fingerprint, resume)
    errors: list[dict] = []
    planned_units = 0
    processed_units = len(completed_units)

    num_files = len(input_paths)
    for i, input_path in enumerate(input_paths, 1):
        file_path = Path(input_path)
        print(f"[{i}/{num_files}] Analisando {file_path.name} (hybrid)...")

        harness_path = harness_for.get(str(file_path.resolve())) if harness_for else None

        # Preprocess converts each Python function into a CodeUnit.
        units = preprocess_file(file_path)
        planned_units += len(units)
        for unit in units:
            unit_key = _unit_key(file_path, unit.qualname)
            if unit_key in completed_units:
                print(f"    - Retomada: {unit.qualname} já concluída; pulando.")
                continue
            # The LLM receives one function at a time and returns zero or more findings.
            try:
                findings = analyzer.analyze(unit)
            except Exception as exc:
                # A single unit failing (e.g. LLM backend exhausted its retries)
                # must not discard every result already collected in this run.
                print(f"    ERRO ao analisar {unit.qualname}: {exc}. Caso pulado, resultados anteriores preservados.")
                errors.append({"unit": unit.qualname, "source_file": str(file_path), "error": str(exc)})
                _write_json_atomic(artifacts_dir / "errors.json", errors)
                continue

            verifiable_findings = [finding for finding in findings if finding.verifiable]
            num_verifiable = len(verifiable_findings)
            verified_count = 0

            for finding in findings:
                esbmc_result = None
                esbmc_direct_result = None

                if finding.verifiable:
                    verified_count += 1
                    print(
                        f"    - Validando hipotese {verified_count}/{num_verifiable}: "
                        f"{finding.category} em {unit.name}..."
                    )
                    if harness_path is not None:
                        # Verify the hidden harness, not the file the LLM saw.
                        esbmc_direct_result = run_esbmc_direct(
                            file_path=harness_path,
                            esbmc_command=esbmc_command,
                            bound=bound,
                            timeout_seconds=timeout_seconds,
                            output_dir=artifacts_dir,
                        )
                    else:
                        # V1 behavior: ESBMC needs the real file path and
                        # function name. This does not mean the LLM saw the
                        # file path in raw mode.
                        esbmc_result = run_esbmc_on_function(
                            file_path=file_path,
                            function_name=unit.name,
                            finding_id=finding.id,
                            category=finding.category,
                            esbmc_command=esbmc_command,
                            bound=bound,
                            timeout_seconds=timeout_seconds,
                            output_dir=artifacts_dir,
                        )

                result = consolidate_result(
                    unit_name=unit.qualname,
                    source_file=str(file_path),
                    finding=finding,
                    esbmc_result=esbmc_result,
                    esbmc_direct_result=esbmc_direct_result,
                )
                results.append(result)

            # Persist after every unit, not only at the end: a crash later in the
            # run (network error, a case that exhausts every retry) must not cost
            # the results already collected for prior units.
            write_json_report(results, artifacts_dir / "report.json")
            completed_units.add(unit_key)
            processed_units += 1
            _write_run_status(
                artifacts_dir, fingerprint, planned_units, processed_units,
                errors, completed_units,
            )

    _write_run_status(
        artifacts_dir, fingerprint, planned_units, processed_units,
        errors, completed_units,
    )

    return results


# ---------------------------------------------------------------------------
# Flow C: LLM-only
# ---------------------------------------------------------------------------

def run_pipeline_llm_only(
    input_paths: Sequence[str | Path],
    output_dir: str | Path = "artifacts/llm-only",
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    google_api_key: str | None = None,
    ollama_base_url: str | None = None,
    timeout_seconds: int = 300,
    resume: bool = False,
) -> list[FinalResult]:
    """Flow C: run the LLM only, without ESBMC confirmation.

    This is the neural baseline. It uses the same preprocessing and prompt
    machinery as Flow B, but every finding is consolidated with llm_only=True
    and no ESBMC command is executed.
    """
    analyzer = build_analyzer(
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        google_api_key=google_api_key,
        ollama_base_url=ollama_base_url,
        timeout_seconds=timeout_seconds,
    )
    artifacts_dir = Path(output_dir)
    fingerprint = _run_fingerprint(
        mode="llm-only", backend=backend, model=getattr(analyzer, "model", llm_model),
        bound=None, timeout=timeout_seconds,
    )
    results, completed_units = _initialize_run(artifacts_dir, fingerprint, resume)
    errors: list[dict] = []
    planned_units = 0
    processed_units = len(completed_units)
    num_files = len(input_paths)
    for i, input_path in enumerate(input_paths, 1):
        file_path = Path(input_path)
        print(f"[{i}/{num_files}] Analisando {file_path.name} (LLM-only)...")

        # Flow C keeps the LLM findings as final suspected results.
        units = preprocess_file(file_path)
        planned_units += len(units)
        for unit in units:
            unit_key = _unit_key(file_path, unit.qualname)
            if unit_key in completed_units:
                print(f"    - Retomada: {unit.qualname} já concluída; pulando.")
                continue
            try:
                findings = analyzer.analyze(unit)
            except Exception as exc:
                print(f"    ERRO ao analisar {unit.qualname}: {exc}. Caso pulado, resultados anteriores preservados.")
                errors.append({"unit": unit.qualname, "source_file": str(file_path), "error": str(exc)})
                _write_json_atomic(artifacts_dir / "errors.json", errors)
                continue

            for finding in findings:
                result = consolidate_result(
                    unit_name=unit.qualname,
                    source_file=str(file_path),
                    finding=finding,
                    esbmc_result=None,
                    llm_only=True,
                )
                results.append(result)

            # Persist after every unit, not only at the end (see Flow B for why).
            write_json_report(results, artifacts_dir / "report.json")
            completed_units.add(unit_key)
            processed_units += 1
            _write_run_status(
                artifacts_dir, fingerprint, planned_units, processed_units,
                errors, completed_units,
            )

    _write_run_status(
        artifacts_dir, fingerprint, planned_units, processed_units,
        errors, completed_units,
    )

    return results


def _prepare_output_dir(artifacts_dir: Path) -> None:
    """Create the output directory and remove state owned by a previous run."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for name in ("report.json", "errors.json", "run_status.json"):
        path = artifacts_dir / name
        if path.exists():
            path.unlink()


def _unit_key(file_path: Path, qualname: str) -> str:
    return f"{file_path.resolve()}::{qualname}"


def _run_fingerprint(
    *, mode: str, backend: str, model: str | None,
    bound: int | None, timeout: int, llm_timeout: int | None = None,
    esbmc_command: list[str] | None = None,
    harness_for: dict[str, Path] | None = None,
) -> dict[str, object]:
    return {
        "mode": mode,
        "backend": backend,
        "model": model,
        "bound": bound,
        "timeout": timeout,
        "llm_timeout": llm_timeout,
        "esbmc_command": esbmc_command or ["esbmc"],
        "harness_for": {
            key: str(value.resolve()) for key, value in sorted((harness_for or {}).items())
        },
    }


def _initialize_run(
    artifacts_dir: Path,
    fingerprint: dict[str, object],
    resume: bool,
) -> tuple[list[FinalResult], set[str]]:
    status_path = artifacts_dir / "run_status.json"
    report_path = artifacts_dir / "report.json"
    if not resume:
        _prepare_output_dir(artifacts_dir)
        return [], set()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if not status_path.exists():
        return [], set()
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("fingerprint") != fingerprint:
        raise ValueError(
            "Não é seguro retomar: a configuração atual difere de run_status.json. "
            "Use outro --output-dir ou execute sem --resume."
        )
    results = _load_json_report(report_path) if report_path.exists() else []
    return results, set(status.get("completed_units", []))


def _load_json_report(path: Path) -> list[FinalResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results: list[FinalResult] = []
    for item in payload:
        finding = Finding(**item["finding"])
        esbmc = ESBMCResult(**item["esbmc_result"]) if item.get("esbmc_result") else None
        direct = (
            ESBMCDirectResult(**item["esbmc_direct_result"])
            if item.get("esbmc_direct_result") else None
        )
        results.append(FinalResult(
            unit_name=item["unit_name"], source_file=item["source_file"],
            finding=finding, esbmc_result=esbmc, esbmc_direct_result=direct,
            final_classification=item["final_classification"],
            interpretation=item["interpretation"],
        ))
    return results


def _write_run_status(
    artifacts_dir: Path,
    fingerprint: dict[str, object],
    planned: int,
    processed: int,
    errors: list[dict],
    completed_units: set[str],
) -> None:
    status = "complete" if not errors and processed == planned else "partial"
    payload = {
        "status": status,
        "fingerprint": fingerprint,
        "planned_units": planned,
        "processed_units": processed,
        "failed_units": len(errors),
        "errors": errors,
        "completed_units": sorted(completed_units),
    }
    _write_json_atomic(artifacts_dir / "run_status.json", payload)


def _write_json_atomic(target: Path, payload: object) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
