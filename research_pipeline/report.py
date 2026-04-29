from __future__ import annotations

import json
from pathlib import Path

from .models import ESBMCResult, FinalResult, Finding, FormalProperty


def _interpretation(
    classification: str,
    finding: Finding,
    formal_property: FormalProperty | None,
    esbmc_result: ESBMCResult | None,
) -> str:
    expr = finding.metadata.get("expression", "")
    cat = finding.category
    conf = finding.confidence
    expr_str = f" ({expr})" if expr else ""

    if classification == "smell_heuristic":
        return (
            f"Smell heurístico de categoria '{cat}' com confiança '{conf}'. "
            "Sem verificação formal — melhoria de qualidade de código."
        )

    if classification == "vulnerability_potential_with_partial_evidence":
        return (
            f"Suspeita de '{cat}'{expr_str} com confiança '{conf}'. "
            "Verificação formal não executada (ESBMC indisponível ou skipped)."
        )

    if classification == "formally_confirmed_bug":
        prop = formal_property.assertion if formal_property else "?"
        return (
            f"Bug formalmente confirmado: '{cat}'{expr_str}. "
            f"O ESBMC violou a propriedade: {prop}. "
            "Existe ao menos um contraexemplo real."
        )

    if classification == "unconfirmed_hypothesis":
        return (
            f"Suspeita de '{cat}'{expr_str} não confirmada pelo ESBMC "
            "dentro do escopo analisado. "
            "Pode ser falso positivo da LLM ou limitação do modelo formal."
        )

    # inconclusive_case
    esbmc_summary = esbmc_result.summary if esbmc_result else "sem detalhes"
    return (
        f"Caso inconclusivo para '{cat}'{expr_str}. "
        f"ESBMC: {esbmc_summary}. "
        "Pode ser limitação da ferramenta, timeout ou erro de modelagem."
    )


def consolidate_result(
    unit_name: str,
    source_file: str,
    finding: Finding,
    formal_property: FormalProperty | None,
    esbmc_result: ESBMCResult | None,
) -> FinalResult:
    if finding.finding_type == "smell_heuristic":
        classification = "smell_heuristic"
    elif esbmc_result is None or esbmc_result.status == "skipped":
        classification = "vulnerability_potential_with_partial_evidence"
    elif esbmc_result.status == "violation_found":
        classification = "formally_confirmed_bug"
    elif esbmc_result.status == "no_violation_found":
        classification = "unconfirmed_hypothesis"
    else:
        classification = "inconclusive_case"

    return FinalResult(
        unit_name=unit_name,
        source_file=source_file,
        finding=finding,
        formal_property=formal_property,
        esbmc_result=esbmc_result,
        final_classification=classification,
        interpretation=_interpretation(classification, finding, formal_property, esbmc_result),
    )


def write_json_report(results: list[FinalResult], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target
