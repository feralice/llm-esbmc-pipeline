from __future__ import annotations

from pathlib import Path
import shutil

from .esbmc_runner import run_esbmc
from .formalizer import formalize_finding
from .instrumenter import instrument_unit
from .llm_analyzer import LLMAnalyzer, MockLLMAnalyzer, OpenAIResponsesAnalyzer
from .models import FinalResult
from .preprocess import preprocess_file
from .report import consolidate_result, write_json_report


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path = "artifacts/research-pipeline",
    esbmc_command: list[str] | None = None,
    llm_backend: str = "mock",
    llm_model: str = "gpt-5.4",
    openai_api_key: str | None = None,
) -> list[FinalResult]:
    units = preprocess_file(input_path)
    analyzer = build_analyzer(
        llm_backend=llm_backend,
        llm_model=llm_model,
        openai_api_key=openai_api_key,
    )
    results: list[FinalResult] = []
    artifacts_dir = Path(output_dir)
    instrumented_dir = artifacts_dir / "instrumented"
    _prepare_output_dir(artifacts_dir)

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
                    finding=finding,
                    formal_property=formal_property,
                    esbmc_result=esbmc_result,
                )
            )

    write_json_report(results, artifacts_dir / "report.json")
    return results


def build_analyzer(
    llm_backend: str,
    llm_model: str,
    openai_api_key: str | None,
) -> LLMAnalyzer:
    if llm_backend == "mock":
        return MockLLMAnalyzer()
    if llm_backend == "openai":
        return OpenAIResponsesAnalyzer(api_key=openai_api_key, model=llm_model)
    raise ValueError(f"Backend de LLM nao suportado: {llm_backend}")


def _prepare_output_dir(artifacts_dir: Path) -> None:
    instrumented_dir = artifacts_dir / "instrumented"
    if instrumented_dir.exists():
        shutil.rmtree(instrumented_dir)
    report_path = artifacts_dir / "report.json"
    if report_path.exists():
        report_path.unlink()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
