from __future__ import annotations

import json
from pathlib import Path

from .models import (
    CLASSIFICATION_ESBMC_INCONCLUSIVE,
    CLASSIFICATION_ESBMC_NATIVE_BUG,
    CLASSIFICATION_HEURISTIC_SMELL,
    CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC,
    CLASSIFICATION_LLM_FALSE_POSITIVE,
    CLASSIFICATION_LLM_MISSED_ESBMC_BUG,
    CLASSIFICATION_LLM_ONLY,
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
)
from .experimental.runtime_harness_validator import (
    HARNESS_NOT_REPRODUCED,
    HARNESS_REPRODUCED,
    HARNESS_WRONG_EXCEPTION,
)


def _interpretation(
    classification: str,
    finding: Finding,
    esbmc_result: ESBMCResult | None,
    esbmc_direct_result: ESBMCDirectResult | None,
) -> str:
    expr = finding.metadata.get("expression", "")
    cat  = finding.category
    conf = finding.confidence
    expr_str = f" ({expr})" if expr else ""

    if classification == CLASSIFICATION_OUT_OF_SCOPE:
        original = finding.metadata.get("original_category", cat)
        return (
            f"Categoria '{original}' fora do escopo do MVP. "
            "Apenas division_by_zero, out_of_bounds, long_method, many_parameters e complex_conditional são aceitas. "
            "Achado descartado da análise principal."
        )

    if classification == CLASSIFICATION_HEURISTIC_SMELL:
        return (
            f"Smell heurístico de categoria '{cat}' com confiança '{conf}'. "
            "Sem verificação formal — problema de qualidade de código."
        )

    if classification == CLASSIFICATION_LLM_FALSE_POSITIVE:
        return (
            f"A LLM apontou '{cat}'{expr_str} como bug verificável, "
            "mas a análise AST não encontrou a operação correspondente no código. "
            "Classificado como falso positivo da LLM (alucinação)."
        )

    if classification == CLASSIFICATION_SKIPPED:
        return (
            f"Achado '{cat}'{expr_str} não pôde ser transformado em propriedade formal "
            "verificável pelo ESBMC no escopo atual do MVP."
        )

    if classification == CLASSIFICATION_LLM_ONLY:
        return (
            f"Bug '{cat}'{expr_str} suspeito pela LLM (Flow C — sem verificação formal). "
            "Não foi executada confirmação via ESBMC."
        )

    if classification == CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC:
        return (
            f"Bug '{cat}'{expr_str} levantado pela LLM e confirmado formalmente pelo ESBMC. "
            "Existe ao menos um contraexemplo concreto."
        )

    if classification == CLASSIFICATION_RUNTIME_REPRODUCED:
        exc = finding.metadata.get("expected_exception", "exceção esperada")
        return (
            f"Bug '{cat}'{expr_str} levantado pela LLM e reproduzido em runtime. "
            f"O harness gerou {exc} com as entradas fornecidas. "
            "Validação via execução controlada (sem verificação formal completa)."
        )

    if classification == CLASSIFICATION_RUNTIME_NOT_REPRODUCED:
        return (
            f"Suspeita de '{cat}'{expr_str} não reproduzida pelo harness de runtime. "
            "O harness executou sem levantar exceção ou levantou exceção diferente da esperada."
        )

    if classification == CLASSIFICATION_RUNTIME_INCONCLUSIVE:
        return (
            f"Harness de runtime inconclusivo para '{cat}'{expr_str}. "
            "Possíveis causas: harness rejeitado por segurança, timeout ou erro de execução."
        )

    if classification == CLASSIFICATION_NOT_CONFIRMED:
        return (
            f"Suspeita de '{cat}'{expr_str} não confirmada pelo ESBMC "
            "dentro do bound analisado. "
            "Pode ser falso positivo da LLM ou limitação do bound definido."
        )

    if classification == CLASSIFICATION_ESBMC_NATIVE_BUG:
        direct_summary = esbmc_direct_result.summary if esbmc_direct_result else ""
        return (
            f"Flow A detectou violação em '{cat}'{expr_str} "
            "sem depender da hipótese da LLM. "
            f"Resultado: {direct_summary}"
        )

    if classification == CLASSIFICATION_LLM_MISSED_ESBMC_BUG:
        direct_summary = esbmc_direct_result.summary if esbmc_direct_result else ""
        return (
            f"Flow A detectou violação que a LLM não apontou ({cat}{expr_str}). "
            f"Resultado: {direct_summary}"
        )

    # esbmc_inconclusive
    esbmc_summary = esbmc_result.summary if esbmc_result else "sem detalhes"
    return (
        f"Caso inconclusivo para '{cat}'{expr_str}. "
        f"ESBMC: {esbmc_summary}. "
        "Pode ser limitação da ferramenta, timeout ou código não suportado."
    )


def consolidate_result(
    unit_name: str,
    source_file: str,
    finding: Finding,
    esbmc_result: ESBMCResult | None,
    esbmc_direct_result: ESBMCDirectResult | None = None,
    harness_result: dict | None = None,
    llm_only: bool = False,
) -> FinalResult:

    finding_type = finding.finding_type

    if finding_type == "out_of_scope_finding":
        classification = CLASSIFICATION_OUT_OF_SCOPE

    elif finding_type == "llm_false_positive":
        classification = CLASSIFICATION_LLM_FALSE_POSITIVE

    elif finding_type == "smell_heuristic":
        classification = CLASSIFICATION_HEURISTIC_SMELL

    elif finding_type == "suspected_bug" and llm_only:
        classification = CLASSIFICATION_LLM_ONLY

    elif finding_type == "suspected_bug":
        # Flow B: ESBMC with --function (esbmc_result always set for verifiable findings)
        if esbmc_result is None or esbmc_result.status == "skipped":
            if esbmc_direct_result and esbmc_direct_result.status == "violation_found":
                classification = CLASSIFICATION_ESBMC_NATIVE_BUG
            else:
                classification = CLASSIFICATION_SKIPPED
        elif esbmc_result.status == "violation_found" and _esbmc_result_matches_category(esbmc_result.details, finding.category):
            classification = CLASSIFICATION_LLM_CONFIRMED_BY_ESBMC
        elif esbmc_result.status == "violation_found":
            classification = CLASSIFICATION_ESBMC_INCONCLUSIVE
        elif esbmc_result.status == "no_violation_found":
            classification = CLASSIFICATION_NOT_CONFIRMED
        else:
            # tool_error, inconclusive, timeout — try harness if available
            if harness_result is not None:
                status = harness_result.get("status", "")
                if status == HARNESS_REPRODUCED:
                    classification = CLASSIFICATION_RUNTIME_REPRODUCED
                elif status in (HARNESS_NOT_REPRODUCED, HARNESS_WRONG_EXCEPTION):
                    classification = CLASSIFICATION_RUNTIME_NOT_REPRODUCED
                else:
                    classification = CLASSIFICATION_RUNTIME_INCONCLUSIVE
            else:
                classification = CLASSIFICATION_ESBMC_INCONCLUSIVE

    else:
        classification = CLASSIFICATION_SKIPPED

    return FinalResult(
        unit_name=unit_name,
        source_file=source_file,
        finding=finding,
        esbmc_result=esbmc_result,
        esbmc_direct_result=esbmc_direct_result,
        harness_result=harness_result,
        final_classification=classification,
        interpretation=_interpretation(
            classification, finding, esbmc_result, esbmc_direct_result
        ),
    )


def make_missed_bug_result(
    source_file: str,
    esbmc_direct_result: ESBMCDirectResult,
) -> FinalResult:
    """Synthetic result for bugs Flow A found but LLM missed entirely."""
    from .models import Finding  # local to avoid circular at module level

    synthetic_finding = Finding(
        id=f"esbmc_direct_{Path(source_file).stem}",
        stage="esbmc_direct",
        finding_type="suspected_bug",
        category="esbmc_detected",
        title="Bug detectado pelo Flow A (não reportado pela LLM)",
        explanation=(
            "O ESBMC rodando diretamente no arquivo original detectou uma violação "
            "que não foi levantada pela LLM. Isso pode indicar falso negativo da LLM."
        ),
        evidence=[esbmc_direct_result.summary],
        verifiable=True,
        confidence="high",
        metadata={
            "expression": str(esbmc_direct_result.details.get("property_kind", "")),
            "line": str(esbmc_direct_result.details.get("location", "")),
            "relative_line": "",
        },
    )

    return FinalResult(
        unit_name="(esbmc_direct)",
        source_file=source_file,
        finding=synthetic_finding,
        esbmc_result=None,
        esbmc_direct_result=esbmc_direct_result,
        final_classification=CLASSIFICATION_LLM_MISSED_ESBMC_BUG,
        interpretation=_interpretation(
            CLASSIFICATION_LLM_MISSED_ESBMC_BUG,
            synthetic_finding,
            None,
            esbmc_direct_result,
        ),
    )


def _esbmc_result_matches_category(details: dict[str, object], expected_category: str) -> bool:
    text = " ".join(
        str(details.get(key, ""))
        for key in ("property_kind", "property_text", "location")
    )
    return _category_from_esbmc_property(text) == expected_category


def _category_from_esbmc_property(text: str) -> str:
    normalized = text.lower()
    if "assertion" in normalized:
        return "assertion_violation"
    if "division_by_zero" in normalized or "division by zero" in normalized or "divisor" in normalized:
        return "division_by_zero"
    if "out-of-bounds" in normalized or "out of bounds" in normalized or "bounds" in normalized:
        return "out_of_bounds"
    return "unknown_esbmc_violation"


def make_direct_observation_result(
    source_file: str,
    esbmc_direct_result: ESBMCDirectResult,
) -> FinalResult:
    """Synthetic non-LLM result used to keep direct ESBMC data in per-file reports."""
    synthetic_finding = Finding(
        id=f"esbmc_direct_{Path(source_file).stem}",
        stage="esbmc_direct",
        finding_type="direct_observation",
        category="esbmc_direct",
        title="Resultado do Flow A",
        explanation=esbmc_direct_result.summary,
        evidence=[esbmc_direct_result.summary],
        verifiable=False,
        confidence="high",
        metadata={
            "expression": str(esbmc_direct_result.details.get("property_kind", "")),
            "line": str(esbmc_direct_result.details.get("location", "")),
            "relative_line": "",
        },
    )

    return FinalResult(
        unit_name="(esbmc_direct)",
        source_file=source_file,
        finding=synthetic_finding,
        esbmc_result=None,
        esbmc_direct_result=esbmc_direct_result,
        final_classification="clean",
        interpretation=esbmc_direct_result.summary,
    )


def write_json_report(results: list[FinalResult], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target
