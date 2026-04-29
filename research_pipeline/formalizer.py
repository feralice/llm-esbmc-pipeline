from __future__ import annotations

import ast
from dataclasses import dataclass

from .models import CodeUnit, Finding, FormalProperty


@dataclass(frozen=True)
class _ESBMCPropertyProfile:
    category: str
    hypothesis: str
    esbmc_flags: list[str]
    notes: str


_PROPERTY_PROFILES: dict[str, _ESBMCPropertyProfile] = {
    "division_by_zero": _ESBMCPropertyProfile(
        category="division_by_zero",
        hypothesis="O denominador deve ser diferente de zero antes da operacao.",
        esbmc_flags=["--no-bounds-check"],
        notes=(
            "Propriedade local gerada a partir de divisao detectada pelo analisador. "
            "Perfil de flags baseado na documentacao do ESBMC: mantem a checagem de divisao "
            "por zero e desabilita bounds-check, que ja e verificado em outro finding."
        ),
    ),
    "out_of_bounds": _ESBMCPropertyProfile(
        category="out_of_bounds",
        hypothesis="O indice deve permanecer dentro dos limites da colecao.",
        esbmc_flags=["--no-div-by-zero-check"],
        notes=(
            "Propriedade local para acesso indexado. Perfil de flags baseado na documentacao "
            "do ESBMC: mantem a checagem de bounds e desabilita divisao por zero, irrelevante "
            "para este finding."
        ),
    ),
}


def formalize_finding(unit: CodeUnit, finding: Finding) -> FormalProperty | None:
    if not finding.verifiable:
        return None

    if finding.category == "division_by_zero":
        profile = _PROPERTY_PROFILES[finding.category]
        expression = finding.metadata.get("expression", "")
        denominator = _extract_denominator(expression)
        assertion = f"({denominator}) != 0" if denominator else "False"
        return FormalProperty(
            finding_id=finding.id,
            category=finding.category,
            hypothesis=profile.hypothesis,
            assertion=assertion,
            assumptions=_build_reachability_assumptions(unit, skip_category="division_by_zero"),
            esbmc_flags=list(profile.esbmc_flags),
            notes=profile.notes,
            insertion_line=_parse_relative_line(finding),
            absolute_line=_parse_absolute_line(finding),
        )

    if finding.category == "out_of_bounds":
        profile = _PROPERTY_PROFILES[finding.category]
        expression = finding.metadata.get("expression", "")
        base, index = _extract_subscript_parts(expression)
        if base and index:
            assertion = f"(0 <= ({index})) and (({index}) < len({base}))"
        else:
            assertion = "False"
        return FormalProperty(
            finding_id=finding.id,
            category=finding.category,
            hypothesis=profile.hypothesis,
            assertion=assertion,
            assumptions=[],
            esbmc_flags=list(profile.esbmc_flags),
            notes=profile.notes,
            insertion_line=_parse_relative_line(finding),
            absolute_line=_parse_absolute_line(finding),
        )

    return None


def _extract_denominator(expression: str) -> str:
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError:
        return ""
    body = parsed.body
    if isinstance(body, ast.BinOp) and isinstance(body.op, (ast.Div, ast.FloorDiv, ast.Mod)):
        return ast.unparse(body.right)
    return ""


def _extract_subscript_parts(expression: str) -> tuple[str, str]:
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError:
        return "", ""
    body = parsed.body
    if not isinstance(body, ast.Subscript):
        return "", ""
    base = ast.unparse(body.value)
    index = ast.unparse(body.slice)
    return base, index


def _parse_relative_line(finding: Finding) -> int | None:
    value = finding.metadata.get("relative_line")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_absolute_line(finding: Finding) -> int | None:
    value = finding.metadata.get("line")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _build_reachability_assumptions(unit: CodeUnit, skip_category: str) -> list[str]:
    assumptions: list[str] = []
    for op in unit.operations:
        if skip_category == "division_by_zero" and op.kind == "subscript":
            base, index = _extract_subscript_parts(op.expression)
            if base and index:
                assumptions.append(f"(0 <= ({index})) and (({index}) < len({base}))")
    return assumptions
