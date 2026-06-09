"""Pipeline executors for the three experimental flows.

src/main.py parses CLI arguments and chooses the mode.
This module only executes the selected flow:

Flow A: ESBMC-only. It discovers functions and runs ESBMC on each one.
Flow B: Hybrid. The LLM proposes findings; ESBMC checks verifiable bugs.
Flow C: LLM-only. The LLM findings are kept without formal confirmation.
"""

from __future__ import annotations

import json
from pathlib import Path

from .llm.backends.factory import Backend, build_analyzer  # noqa: F401 - re-exported
from .llm.prompts import PromptMode
from .models import ESBMCDirectResult, FinalResult
from .preprocess import preprocess_file
from .report import consolidate_result, write_json_report
from .verification.esbmc_runner import run_esbmc_function_baseline, run_esbmc_on_function


# ---------------------------------------------------------------------------
# Flow A: ESBMC-only
# ---------------------------------------------------------------------------

def run_pipeline_esbmc_direct(
    input_paths: list[str | Path],
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
    summary_path.write_text(
        json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
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
    prompt_mode: PromptMode = "raw",
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
        ollama_base_url=ollama_base_url,
        bound=bound,
        timeout_seconds=timeout_seconds,
        prompt_mode=prompt_mode,
    )


def run_pipeline_multi(
    input_paths: list[str | Path],
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
    prompt_mode: PromptMode = "raw",
) -> list[FinalResult]:
    """Flow B: LLM proposes findings; ESBMC checks verifiable bug findings.

    For each Python function:
    1. preprocess_file() creates a CodeUnit.
    2. analyzer.analyze() sends that CodeUnit to the LLM.
    3. Verifiable bug findings are checked with ESBMC.
    4. report.consolidate_result() turns each finding into a FinalResult.

    The pipeline keeps file_path internally so ESBMC can run on the real file.
    In prompt_mode="raw", the prompt builder intentionally omits the path from
    the LLM prompt to avoid dataset-category leakage.
    """
    analyzer = build_analyzer(
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        google_api_key=google_api_key,
        ollama_base_url=ollama_base_url,
        timeout_seconds=llm_timeout_seconds,
        prompt_mode=prompt_mode,
    )
    artifacts_dir = Path(output_dir)
    _prepare_output_dir(artifacts_dir)

    results: list[FinalResult] = []

    num_files = len(input_paths)
    for i, input_path in enumerate(input_paths, 1):
        file_path = Path(input_path)
        print(f"[{i}/{num_files}] Analisando {file_path.name} (hybrid)...")

        # Preprocess converts each Python function into a CodeUnit.
        units = preprocess_file(file_path)
        for unit in units:
            # The LLM receives one function at a time and returns zero or more findings.
            findings = analyzer.analyze(unit)
            verifiable_findings = [finding for finding in findings if finding.verifiable]
            num_verifiable = len(verifiable_findings)
            verified_count = 0

            for finding in findings:
                esbmc_result = None

                if finding.verifiable:
                    verified_count += 1
                    print(
                        f"    - Validando hipotese {verified_count}/{num_verifiable}: "
                        f"{finding.category} em {unit.name}..."
                    )
                    # ESBMC needs the real file path and function name. This
                    # does not mean the LLM saw the file path in raw mode.
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
                )
                results.append(result)

    write_json_report(results, artifacts_dir / "report.json")
    return results


# ---------------------------------------------------------------------------
# Flow C: LLM-only
# ---------------------------------------------------------------------------

def run_pipeline_llm_only(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/llm-only",
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    google_api_key: str | None = None,
    ollama_base_url: str | None = None,
    timeout_seconds: int = 300,
    prompt_mode: PromptMode = "raw",
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
        prompt_mode=prompt_mode,
    )
    artifacts_dir = Path(output_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    results: list[FinalResult] = []
    num_files = len(input_paths)
    for i, input_path in enumerate(input_paths, 1):
        file_path = Path(input_path)
        print(f"[{i}/{num_files}] Analisando {file_path.name} (LLM-only)...")

        # Flow C keeps the LLM findings as final suspected results.
        for unit in preprocess_file(file_path):
            for finding in analyzer.analyze(unit):
                result = consolidate_result(
                    unit_name=unit.qualname,
                    source_file=str(file_path),
                    finding=finding,
                    esbmc_result=None,
                    llm_only=True,
                )
                results.append(result)

    write_json_report(results, artifacts_dir / "report.json")
    return results


def _prepare_output_dir(artifacts_dir: Path) -> None:
    """Create the output directory and replace the old report.json if present."""
    report_path = artifacts_dir / "report.json"
    if report_path.exists():
        report_path.unlink()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
