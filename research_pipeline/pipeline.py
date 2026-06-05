from __future__ import annotations

from pathlib import Path
from typing import Literal

from .llm.backends.factory import Backend, build_analyzer  # noqa: F401 — re-exported
from .llm.protocols import LLMAnalyzer
from .models import (
    CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC,
    CLASSIFICATION_ESBMC_NATIVE_BUG,
    ESBMCDirectResult,
    FinalResult,
)
from .preprocess import preprocess_file
from .report import consolidate_result, make_direct_observation_result, make_missed_bug_result, write_json_report
from .verification.esbmc_runner import run_esbmc_function_baseline, run_esbmc_on_function


# ---------------------------------------------------------------------------
# Flow A: ESBMC-only function baseline
# ---------------------------------------------------------------------------

def run_pipeline_esbmc_direct(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/esbmc-direct",
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
) -> list[ESBMCDirectResult]:
    """Flow A: run ESBMC with --function for each function, no LLM involved."""
    results: list[ESBMCDirectResult] = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for input_path in input_paths:
        file_path = Path(input_path)
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

    # Save direct results summary
    import json
    summary_path = Path(output_dir) / "esbmc_direct_results.json"
    summary_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return results


# ---------------------------------------------------------------------------
# Flow B: LLM-first (existing pipeline, now accepts esbmc_direct_result)
# ---------------------------------------------------------------------------

def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path = "artifacts/research-pipeline",
    esbmc_command: list[str] | None = None,
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_base_url: str | None = None,
    esbmc_direct_result: ESBMCDirectResult | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
) -> list[FinalResult]:
    """Flow B: LLM-first hybrid for a single file."""
    return run_pipeline_multi(
        input_paths=[input_path],
        output_dir=output_dir,
        esbmc_command=esbmc_command,
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        ollama_base_url=ollama_base_url,
        esbmc_direct_results={str(Path(input_path)): esbmc_direct_result}
        if esbmc_direct_result else None,
        bound=bound,
        timeout_seconds=timeout_seconds,
    )


def run_pipeline_multi(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/research-pipeline",
    esbmc_command: list[str] | None = None,
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_base_url: str | None = None,
    esbmc_direct_results: dict[str, ESBMCDirectResult] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
) -> list[FinalResult]:
    """Flow B: LLM-first hybrid for multiple files."""
    analyzer = build_analyzer(
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        ollama_base_url=ollama_base_url,
    )
    artifacts_dir = Path(output_dir)
    _prepare_output_dir(artifacts_dir)

    results: list[FinalResult] = []

    for input_path in input_paths:
        file_path = Path(input_path)
        direct = (esbmc_direct_results or {}).get(str(file_path))

        units = preprocess_file(file_path)
        file_results: list[FinalResult] = []

        for unit in units:
            findings = analyzer.analyze(unit)
            for finding in findings:
                esbmc_result = None

                if finding.verifiable:
                    # Flow B: ESBMC with --function, parameters become symbolic automatically
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
                    esbmc_direct_result=direct,
                )
                file_results.append(result)

        # Fix 7: check per-function — each Flow A violation not covered by LLM gets its own entry.
        if direct and direct.status == "violation_found":
            confirmed_functions = {
                r.finding.metadata.get("function", "")
                for r in file_results
                if r.final_classification in (
                    CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC,
                    CLASSIFICATION_ESBMC_NATIVE_BUG,
                )
            }
            for fn_info in direct.details.get("functions", []):
                if not isinstance(fn_info, dict) or fn_info.get("status") != "violation_found":
                    continue
                fn_name = fn_info.get("name", "")
                if fn_name not in confirmed_functions:
                    file_results.append(make_missed_bug_result(str(file_path), direct, fn_info))

        if direct and not file_results:
            file_results.append(make_direct_observation_result(str(file_path), direct))

        results.extend(file_results)

    write_json_report(results, artifacts_dir / "report.json")
    return results


# ---------------------------------------------------------------------------
# Flow C: LLM-only (no ESBMC, baseline)
# ---------------------------------------------------------------------------

def run_pipeline_llm_only(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/llm-only",
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_base_url: str | None = None,
) -> list[FinalResult]:
    """Flow C: LLM-first without ESBMC confirmation (baseline for comparison)."""
    analyzer = build_analyzer(
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        ollama_base_url=ollama_base_url,
    )
    artifacts_dir = Path(output_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    results: list[FinalResult] = []
    for input_path in input_paths:
        file_path = Path(input_path)
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


# ---------------------------------------------------------------------------
# Full pipeline: Flow A + Flow B combined
# ---------------------------------------------------------------------------

def run_full_pipeline(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/full-pipeline",
    esbmc_command: list[str] | None = None,
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_base_url: str | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
) -> list[FinalResult]:
    """
    Full pipeline: runs Flow A (ESBMC-only --function) then Flow B (LLM-first) for each file.
    Combines results so the final JSON has both Flow A and hybrid outcomes.
    """
    artifacts_dir = Path(output_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Flow A: ESBMC-only with --function on all discovered functions
    direct_results: dict[str, ESBMCDirectResult] = {}
    for input_path in input_paths:
        file_path = Path(input_path)
        units = preprocess_file(file_path)
        direct = run_esbmc_function_baseline(
            file_path=file_path,
            function_names=[unit.name for unit in units],
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
            output_dir=artifacts_dir,
        )
        direct_results[str(file_path)] = direct

    # Flow B: LLM-first with Flow A results available for context
    results = run_pipeline_multi(
        input_paths=input_paths,
        output_dir=output_dir,
        esbmc_command=esbmc_command,
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        ollama_base_url=ollama_base_url,
        esbmc_direct_results=direct_results,
        bound=bound,
        timeout_seconds=timeout_seconds,
    )

    return results


def _prepare_output_dir(artifacts_dir: Path) -> None:
    report_path = artifacts_dir / "report.json"
    if report_path.exists():
        report_path.unlink()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
