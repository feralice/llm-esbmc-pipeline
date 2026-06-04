from __future__ import annotations

from pathlib import Path
import shutil
from typing import Literal

from .experimental.runtime_harness_validator import validate_harness
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
from .verification.esbmc_runner import run_esbmc, run_esbmc_direct
from .verification.formalizer import formalize_finding
from .verification.instrumenter import instrument_unit


# ---------------------------------------------------------------------------
# Flow A: ESBMC direct only
# ---------------------------------------------------------------------------

def run_pipeline_esbmc_direct(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/esbmc-direct",
    esbmc_command: list[str] | None = None,
    bound: int = 5,
    timeout_seconds: int = 30,
) -> list[ESBMCDirectResult]:
    """Flow A: run ESBMC directly on every file, no LLM involved."""
    results: list[ESBMCDirectResult] = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for input_path in input_paths:
        file_path = Path(input_path)
        result = run_esbmc_direct(
            file_path,
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
    timeout_seconds: int = 30,
    enable_harness: bool = False,
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
        timeout_seconds=timeout_seconds,
        enable_harness=enable_harness,
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
    timeout_seconds: int = 30,
    enable_harness: bool = False,
) -> list[FinalResult]:
    """Flow B: LLM-first hybrid for multiple files.

    Args:
        enable_harness: Se True, executa harness runtime como fallback quando o
            Formalizer não consegue gerar propriedade formal. Desabilitado por padrão
            na V1 — as métricas do artigo focam em confirmação ESBMC formal.
    """
    analyzer = build_analyzer(
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
        ollama_base_url=ollama_base_url,
    )
    artifacts_dir = Path(output_dir)
    instrumented_dir = artifacts_dir / "instrumented"
    _prepare_output_dir(artifacts_dir)

    results: list[FinalResult] = []

    for input_path in input_paths:
        file_path = Path(input_path)
        direct = (esbmc_direct_results or {}).get(str(file_path))

        units = preprocess_file(file_path)
        file_results: list[FinalResult] = []

        source_code = file_path.read_text(encoding="utf-8")

        for unit in units:
            findings = analyzer.analyze(unit)
            for finding in findings:
                formal_property = formalize_finding(unit, finding)
                esbmc_result = None
                harness_result = None

                if formal_property is not None:
                    # Primary path: ESBMC formal verification
                    instrumentation = instrument_unit(unit, formal_property, instrumented_dir)
                    esbmc_result = run_esbmc(
                        instrumentation,
                        esbmc_command=esbmc_command,
                        timeout_seconds=timeout_seconds,
                    )
                elif (
                    enable_harness
                    and finding.verifiable
                    and finding.metadata.get("reproduction_harness")
                ):
                    # Fallback experimental: harness runtime para padrões que o Formalizer
                    # não consegue formalizar. Desabilitado por padrão na V1.
                    harness_result_obj = validate_harness(
                        source_code=source_code,
                        function_name=unit.name,
                        harness_body=finding.metadata["reproduction_harness"],
                        expected_exception=finding.metadata.get("expected_exception", ""),
                        timeout_seconds=min(timeout_seconds, 10.0),
                    )
                    harness_result = harness_result_obj.to_dict()

                result = consolidate_result(
                    unit_name=unit.qualname,
                    source_file=str(file_path),
                    finding=finding,
                    formal_property=formal_property,
                    esbmc_result=esbmc_result,
                    esbmc_direct_result=direct,
                    harness_result=harness_result,
                )
                file_results.append(result)

        # Check: did ESBMC direct find a bug that LLM missed completely?
        if direct and direct.status == "violation_found":
            llm_confirmed = any(
                r.final_classification in (
                    CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC,
                    CLASSIFICATION_ESBMC_NATIVE_BUG,
                )
                for r in file_results
            )
            if not llm_confirmed:
                file_results.append(make_missed_bug_result(str(file_path), direct))

        if direct and not file_results:
            file_results.append(make_direct_observation_result(str(file_path), direct))

        results.extend(file_results)

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
    enable_harness: bool = False,
) -> list[FinalResult]:
    """
    Full pipeline: runs Flow A (ESBMC direct) then Flow B (LLM-first) for each file.
    Combines results so the final JSON has both ESBMC direct and hybrid outcomes.
    """
    artifacts_dir = Path(output_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Flow A: ESBMC direct on all files
    direct_results: dict[str, ESBMCDirectResult] = {}
    for input_path in input_paths:
        file_path = Path(input_path)
        direct = run_esbmc_direct(
            file_path,
            esbmc_command=esbmc_command,
            bound=bound,
            timeout_seconds=timeout_seconds,
            output_dir=artifacts_dir,
        )
        direct_results[str(file_path)] = direct

    # Flow B: LLM-first with ESBMC direct results available for context
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
        timeout_seconds=timeout_seconds,
        enable_harness=enable_harness,
    )

    return results


def _prepare_output_dir(artifacts_dir: Path) -> None:
    instrumented_dir = artifacts_dir / "instrumented"
    if instrumented_dir.exists():
        shutil.rmtree(instrumented_dir)
    report_path = artifacts_dir / "report.json"
    if report_path.exists():
        report_path.unlink()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
