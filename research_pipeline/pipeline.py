from __future__ import annotations

from pathlib import Path
import shutil
from typing import Literal

from .esbmc_runner import run_esbmc
from .formalizer import formalize_finding
from .instrumenter import instrument_unit
from .llm_analyzer import AnthropicAnalyzer, LLMAnalyzer, OpenAIResponsesAnalyzer
from .models import FinalResult
from .preprocess import preprocess_file
from .report import consolidate_result, write_json_report

Backend = Literal["openai", "anthropic"]

_DEFAULT_MODEL: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-6",
}


def build_analyzer(
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> LLMAnalyzer:
    model = llm_model or _DEFAULT_MODEL[backend]
    if backend == "openai":
        return OpenAIResponsesAnalyzer(api_key=openai_api_key, model=model)
    if backend == "anthropic":
        return AnthropicAnalyzer(api_key=anthropic_api_key, model=model)
    raise ValueError(f"Backend desconhecido: {backend!r}. Use 'openai' ou 'anthropic'.")


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path = "artifacts/research-pipeline",
    esbmc_command: list[str] | None = None,
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> list[FinalResult]:
    """Analisa um único arquivo Python pelo pipeline LLM + ESBMC."""
    return run_pipeline_multi(
        input_paths=[input_path],
        output_dir=output_dir,
        esbmc_command=esbmc_command,
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
    )


def run_pipeline_multi(
    input_paths: list[str | Path],
    output_dir: str | Path = "artifacts/research-pipeline",
    esbmc_command: list[str] | None = None,
    backend: Backend = "openai",
    llm_model: str | None = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> list[FinalResult]:
    """Analisa múltiplos arquivos Python pelo pipeline LLM + ESBMC."""
    analyzer = build_analyzer(
        backend=backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
        anthropic_api_key=anthropic_api_key,
    )
    artifacts_dir = Path(output_dir)
    instrumented_dir = artifacts_dir / "instrumented"
    _prepare_output_dir(artifacts_dir)

    results: list[FinalResult] = []
    for input_path in input_paths:
        file_path = Path(input_path)
        units = preprocess_file(file_path)
        for unit in units:
            findings = analyzer.analyze(unit)
            for finding in findings:
                formal_property = formalize_finding(unit, finding)
                esbmc_result = None
                if formal_property is not None:
                    instrumentation = instrument_unit(unit, formal_property, instrumented_dir)
                    esbmc_result = run_esbmc(instrumentation, esbmc_command=esbmc_command)
                results.append(
                    consolidate_result(
                        unit_name=unit.qualname,
                        source_file=str(file_path),
                        finding=finding,
                        formal_property=formal_property,
                        esbmc_result=esbmc_result,
                    )
                )

    write_json_report(results, artifacts_dir / "report.json")
    return results


def _prepare_output_dir(artifacts_dir: Path) -> None:
    instrumented_dir = artifacts_dir / "instrumented"
    if instrumented_dir.exists():
        shutil.rmtree(instrumented_dir)
    report_path = artifacts_dir / "report.json"
    if report_path.exists():
        report_path.unlink()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
