"""full_report.py — Builds the stable per-file JSON report for the hybrid pipeline.

This module takes the flat list[FinalResult] from pipeline.run_full_pipeline()
and reorganises it into the hierarchical structure expected by the frontend:

  experiment → ground_truth → summary → files[]
                                          ├── esbmc_direct
                                          └── llm_results[]
                                                ├── ast_validation
                                                ├── formal_property
                                                └── esbmc_instrumented
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .evaluator import load_ground_truth_cases
from .models import (
    CLASSIFICATION_ESBMC_INCONCLUSIVE,
    CLASSIFICATION_ESBMC_NATIVE_BUG,
    CLASSIFICATION_HEURISTIC_SMELL,
    CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC,
    CLASSIFICATION_LLM_FALSE_POSITIVE,
    CLASSIFICATION_LLM_MISSED_ESBMC_BUG,
    CLASSIFICATION_NOT_CONFIRMED,
    CLASSIFICATION_OUT_OF_SCOPE,
    CLASSIFICATION_RUNTIME_INCONCLUSIVE,
    CLASSIFICATION_RUNTIME_NOT_REPRODUCED,
    CLASSIFICATION_RUNTIME_REPRODUCED,
    CLASSIFICATION_SKIPPED,
    ESBMCDirectResult,
    ESBMCResult,
    FinalResult,
    Finding,
    FormalProperty,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_full_report(
    input_paths: list[Path],
    results: list[FinalResult],
    mode: str = "full",
    model: str | None = None,
    bound: int = 5,
    timeout: int = 30,
    ground_truth_path: Path | None = None,
) -> dict:
    """Organise a flat list[FinalResult] into the stable per-file report dict."""

    gt_by_file = _ground_truth_by_file(ground_truth_path)

    # Index results by resolved source_file path
    by_file: dict[str, list[FinalResult]] = {}
    for r in results:
        key = str(Path(r.source_file).resolve())
        by_file.setdefault(key, []).append(r)

    file_entries: list[dict] = []
    for input_path in input_paths:
        src_key = str(input_path.resolve())
        file_results = by_file.get(src_key, [])

        # All findings in a file share the same esbmc_direct_result
        direct: ESBMCDirectResult | None = _first_direct(file_results)

        # LLM findings: everything except synthetic "esbmc_direct" stage entries
        llm_results = [
            _finding_to_result(r, model)
            for r in file_results
            if r.finding.stage != "esbmc_direct"
        ]

        try:
            source_code = input_path.read_text(encoding="utf-8")
        except OSError:
            source_code = ""

        file_entries.append({
            "file": str(input_path.resolve()),
            "source_code": source_code,
            "ground_truth_findings": gt_by_file.get(str(input_path.resolve()), []),
            "esbmc_direct": _direct_dict(direct),
            "llm_results": llm_results,
            "final_file_classification": _classify_file(file_results),
        })

    return {
        "experiment": _experiment_block(mode, model, input_paths, bound, timeout),
        "ground_truth": _ground_truth_block(ground_truth_path),
        "summary": _summary_block(file_entries),
        "files": file_entries,
    }


def write_full_report(report: dict, output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


# ---------------------------------------------------------------------------
# Experiment / ground-truth / summary blocks
# ---------------------------------------------------------------------------

def _experiment_block(
    mode: str,
    model: str | None,
    input_paths: list[Path],
    bound: int,
    timeout: int,
) -> dict:
    return {
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": str(input_paths[0].parent.resolve()) if input_paths else "",
        "model": model or "(não especificado)",
        "bound": bound,
        "timeout": timeout,
    }


def _ground_truth_block(gt_path: Path | None) -> dict:
    if gt_path is None or not gt_path.exists():
        return {
            "provided": False,
            "path": str(gt_path) if gt_path else None,
            "evaluation_status": "skipped",
            "message": "Ground truth was not provided. Metrics were not calculated.",
        }
    cases = load_ground_truth_cases(gt_path)
    return {
        "provided": True,
        "path": str(gt_path.resolve()),
        "total_files": len(cases),
        "total_expected_findings": sum(len(expected) for _, expected in cases),
        "evaluation_status": "pending",
        "message": "Ground truth provided but full evaluation is not implemented in this mode.",
    }


def _ground_truth_by_file(gt_path: Path | None) -> dict[str, list[dict]]:
    if gt_path is None or not gt_path.exists():
        return {}
    return {
        str(file_path.resolve()): expected
        for file_path, expected in load_ground_truth_cases(gt_path)
    }


def _summary_block(file_entries: list[dict]) -> dict:
    all_llm: list[dict] = [lr for e in file_entries for lr in e["llm_results"]]
    return {
        "total_files": len(file_entries),
        "total_llm_findings": len(all_llm),
        "total_esbmc_direct_violations": sum(
            1 for e in file_entries
            if (e["esbmc_direct"] or {}).get("status") == "violation_found"
        ),
        "total_no_vcc_generated": sum(
            1 for e in file_entries
            if (e["esbmc_direct"] or {}).get("status") == "no_vcc_generated"
        ),
        "total_confirmed_by_esbmc": sum(
            1 for lr in all_llm
            if lr["final_classification"] == CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC
        ),
        "total_llm_false_positives": sum(
            1 for lr in all_llm
            if lr["final_classification"] == CLASSIFICATION_LLM_FALSE_POSITIVE
        ),
        "total_smells": sum(
            1 for lr in all_llm
            if lr["final_classification"] == CLASSIFICATION_HEURISTIC_SMELL
        ),
        "total_out_of_scope_findings": sum(
            1 for lr in all_llm
            if lr["final_classification"] == CLASSIFICATION_OUT_OF_SCOPE
        ),
        "total_runtime_reproduced": sum(
            1 for lr in all_llm
            if lr["final_classification"] == CLASSIFICATION_RUNTIME_REPRODUCED
        ),
        "total_inconclusive": sum(
            1 for lr in all_llm
            if lr["final_classification"] in (
                CLASSIFICATION_ESBMC_INCONCLUSIVE,
                CLASSIFICATION_NOT_CONFIRMED,
                CLASSIFICATION_SKIPPED,
                CLASSIFICATION_RUNTIME_NOT_REPRODUCED,
                CLASSIFICATION_RUNTIME_INCONCLUSIVE,
            )
        ),
    }


# ---------------------------------------------------------------------------
# Per-file helpers
# ---------------------------------------------------------------------------

def _first_direct(file_results: list[FinalResult]) -> ESBMCDirectResult | None:
    for r in file_results:
        if r.esbmc_direct_result is not None:
            return r.esbmc_direct_result
    return None


def _classify_file(results: list[FinalResult]) -> str:
    """Roll up individual classifications into a single file-level verdict."""
    cls_set = {r.final_classification for r in results}
    # Priority order: worst first
    for cls in (
        CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC,
        CLASSIFICATION_ESBMC_NATIVE_BUG,
        CLASSIFICATION_LLM_MISSED_ESBMC_BUG,
        CLASSIFICATION_RUNTIME_REPRODUCED,
        CLASSIFICATION_LLM_FALSE_POSITIVE,
        CLASSIFICATION_NOT_CONFIRMED,
        CLASSIFICATION_RUNTIME_NOT_REPRODUCED,
        CLASSIFICATION_ESBMC_INCONCLUSIVE,
        CLASSIFICATION_RUNTIME_INCONCLUSIVE,
        CLASSIFICATION_OUT_OF_SCOPE,
        CLASSIFICATION_HEURISTIC_SMELL,
        CLASSIFICATION_SKIPPED,
    ):
        if cls in cls_set:
            return cls
    return "clean"


def _direct_dict(direct: ESBMCDirectResult | None) -> dict | None:
    if direct is None:
        return None
    zero_vccs = bool(direct.details.get("zero_vccs", False))
    return {
        "status": direct.status,
        "command": direct.command,
        "return_code": direct.returncode,
        "time_seconds": direct.time_seconds,
        "summary": direct.summary,
        "property_kind": direct.details.get("property_kind", ""),
        "location": direct.details.get("location", ""),
        "counterexample": direct.details.get("counterexample", []),
        "zero_vccs": zero_vccs,
        "generated_vcc_count": direct.details.get("generated_vcc_count"),
        "bound": direct.details.get("bound", 0),
        "observation": (
            "ESBMC retornou SUCCESSFUL, mas nao gerou VCCs; este resultado nao e tratado como prova de ausencia de violacao."
            if zero_vccs else ""
        ),
        "stdout_path": direct.raw_log_path,
        # stdout and stderr are combined in the same log file
        "stderr_path": direct.raw_log_path,
    }


# ---------------------------------------------------------------------------
# Per-finding helpers
# ---------------------------------------------------------------------------

def _finding_to_result(result: FinalResult, model: str | None) -> dict:
    f = result.finding
    instr_file = _instrumented_file_path(result.esbmc_result)
    out_of_scope = result.final_classification == CLASSIFICATION_OUT_OF_SCOPE
    cls = result.final_classification
    validation_strategy = _validation_strategy(result)
    return {
        "model": model or "(não especificado)",
        "function": result.unit_name,
        "category": f.category,
        "original_category": f.metadata.get("original_category", f.category),
        "mvp_scope": not out_of_scope,
        "discard_reason": "category_outside_mvp" if out_of_scope else "",
        "type": f.finding_type,
        "line": _safe_int(f.metadata.get("line")),
        "expression": f.metadata.get("expression", ""),
        "confidence": f.confidence,
        "reasoning": f.explanation,
        "evidence": f.evidence,
        "verifiable": f.verifiable,
        "validation_strategy": validation_strategy,
        "expected_exception": f.metadata.get("expected_exception", ""),
        "reproduction_harness": f.metadata.get("reproduction_harness", ""),
        "ast_validation": _ast_validation(f),
        "formal_property": _formal_prop_dict(result.formal_property),
        "instrumented_file": instr_file,
        "esbmc_instrumented": _esbmc_instrumented_dict(result.esbmc_result),
        "runtime_validation": result.harness_result,
        "final_classification": cls,
        "interpretation": result.interpretation,
    }


def _validation_strategy(result: FinalResult) -> str:
    if result.esbmc_result is not None:
        return "esbmc"
    if result.harness_result is not None:
        return "runtime_harness"
    if result.finding.finding_type == "smell_heuristic":
        return "heuristic"
    return "skipped"


def _ast_validation(finding: Finding) -> dict:
    ft = finding.finding_type
    has_guard = finding.metadata.get("has_guard", "false") == "true"
    ast_unrecognized = finding.metadata.get("ast_unrecognized", "false") == "true"

    if ft == "suspected_bug":
        if ast_unrecognized:
            reason = (
                "Expressão encontrada no código como nó AST executável, mas padrão não "
                "reconhecido pelo analisador. Encaminhado ao Formalizer/harness."
            )
        elif has_guard:
            reason = (
                "Operação confirmada no AST pelo preprocess. "
                "Guarda detectada — ESBMC poderá não encontrar violação."
            )
        else:
            reason = "Operação confirmada no AST pelo preprocess."
        return {
            "valid": True,
            "reason": reason,
            "has_guard": has_guard,
            "ast_unrecognized": ast_unrecognized,
        }

    if ft == "llm_false_positive":
        return {
            "valid": False,
            "reason": "Operação não encontrada no AST — possível alucinação da LLM.",
            "has_guard": False,
        }
    if ft == "smell_heuristic":
        return {
            "valid": True,
            "reason": "Smell heurístico — validação AST não aplicável.",
            "has_guard": False,
        }
    return {
        "valid": False,
        "reason": (
            "Categoria fora do escopo do MVP; achado descartado da analise principal."
            if ft == "out_of_scope_finding"
            else f"Tipo de achado não reconhecido: {ft}"
        ),
        "has_guard": False,
    }


def _formal_prop_dict(prop: FormalProperty | None) -> dict:
    if prop is None:
        return {"supported": False, "property": None, "assertion": None}
    return {
        "supported": True,
        "property": prop.hypothesis,
        "assertion": prop.assertion,
        "assumptions": prop.assumptions,
        "esbmc_flags": prop.esbmc_flags,
    }


def _esbmc_instrumented_dict(esbmc: ESBMCResult | None) -> dict | None:
    if esbmc is None:
        return None
    return {
        "status": esbmc.status,
        "command": esbmc.command,
        "return_code": esbmc.returncode,
        "time_seconds": 0.0,   # ESBMCResult does not track elapsed time
        "summary": esbmc.summary,
        "property_kind": esbmc.details.get("property_kind", ""),
        "counterexample": esbmc.details.get("counterexample", []),
        "stdout_path": esbmc.raw_log_path,
    }


def _instrumented_file_path(esbmc: ESBMCResult | None) -> str | None:
    """Extract the instrumented .py path from the ESBMC command (always the last argument)."""
    if esbmc is None or not esbmc.command:
        return None
    candidate = esbmc.command[-1]
    if candidate.endswith(".py"):
        return candidate
    return None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _safe_int(value: str | None) -> int:
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0
