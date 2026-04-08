from __future__ import annotations

import json
from pathlib import Path

from .models import ESBMCResult, FinalResult, Finding, FormalProperty


def consolidate_result(
    unit_name: str,
    finding: Finding,
    formal_property: FormalProperty | None,
    esbmc_result: ESBMCResult | None,
) -> FinalResult:
    if finding.finding_type == "smell_heuristic":
        return FinalResult(
            unit_name=unit_name,
            finding=finding,
            formal_property=formal_property,
            esbmc_result=esbmc_result,
            final_classification="smell_heuristic",
            interpretation="Achado heuristico explicado pelo analisador, sem prova formal direta.",
        )

    if esbmc_result is None or esbmc_result.status == "skipped":
        return FinalResult(
            unit_name=unit_name,
            finding=finding,
            formal_property=formal_property,
            esbmc_result=esbmc_result,
            final_classification="vulnerability_potential_with_partial_evidence",
            interpretation="Ha suspeita relevante, mas a validacao formal nao foi executada.",
        )

    if esbmc_result.status == "violation_found":
        return FinalResult(
            unit_name=unit_name,
            finding=finding,
            formal_property=formal_property,
            esbmc_result=esbmc_result,
            final_classification="formally_confirmed_bug",
            interpretation="A hipotese heuristica foi convertida em propriedade e violada pelo ESBMC.",
        )

    if esbmc_result.status == "no_violation_found":
        return FinalResult(
            unit_name=unit_name,
            finding=finding,
            formal_property=formal_property,
            esbmc_result=esbmc_result,
            final_classification="unconfirmed_hypothesis",
            interpretation="Nao houve confirmacao da suspeita dentro do escopo analisado.",
        )

    return FinalResult(
        unit_name=unit_name,
        finding=finding,
        formal_property=formal_property,
        esbmc_result=esbmc_result,
        final_classification="inconclusive_case",
        interpretation="A suspeita nao pode ser decidida por limitacoes da ferramenta ou da modelagem.",
    )


def write_json_report(results: list[FinalResult], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target
