from __future__ import annotations

import ast
from dataclasses import dataclass

from ..models import CodeUnit, Finding, FormalProperty


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
    "assertion_violation": _ESBMCPropertyProfile(
        category="assertion_violation",
        hypothesis="A execucao nao deve alcancar uma assercao falsa ou raise AssertionError.",
        esbmc_flags=[],
        notes=(
            "Propriedade local para caminhos que chegam a assert falso ou raise AssertionError. "
            "Mantem checagens nativas do ESBMC habilitadas."
        ),
    ),
}


def formalize_finding(unit: CodeUnit, finding: Finding) -> FormalProperty | None:
    if not finding.verifiable:
        return None

    if finding.category == "division_by_zero":
        return _formalize_division_by_zero(unit, finding)

    if finding.category == "out_of_bounds":
        return _formalize_out_of_bounds(finding)

    if finding.category == "assertion_violation":
        return _formalize_assertion_violation(finding)

    return None


def _formalize_division_by_zero(unit: CodeUnit, finding: Finding) -> FormalProperty | None:
    profile = _PROPERTY_PROFILES[finding.category]
    expression = finding.metadata.get("expression", "")
    denominator = _extract_denominator(expression)
    if not denominator:
        return None
    return _build_formal_property(
        finding=finding,
        profile=profile,
        assertion=f"({denominator}) != 0",
        assumptions=_build_reachability_assumptions(unit, skip_category="division_by_zero"),
    )


def _formalize_out_of_bounds(finding: Finding) -> FormalProperty | None:
    profile = _PROPERTY_PROFILES[finding.category]
    expression = finding.metadata.get("expression", "")
    base, index = _extract_subscript_parts(expression)
    if not base or not index:
        return None
    return _build_formal_property(
        finding=finding,
        profile=profile,
        assertion=f"(0 <= ({index})) and (({index}) < len({base}))",
        assumptions=[],
    )


def _formalize_assertion_violation(finding: Finding) -> FormalProperty | None:
    profile = _PROPERTY_PROFILES[finding.category]
    expression = finding.metadata.get("expression", "")
    assertion = _assertion_property_from_expression(expression)
    if not assertion:
        return None
    return _build_formal_property(
        finding=finding,
        profile=profile,
        assertion=assertion,
        assumptions=[],
    )


def _build_formal_property(
    finding: Finding,
    profile: _ESBMCPropertyProfile,
    assertion: str,
    assumptions: list[str],
) -> FormalProperty:
    return FormalProperty(
        finding_id=finding.id,
        category=finding.category,
        hypothesis=profile.hypothesis,
        assertion=assertion,
        assumptions=assumptions,
        esbmc_flags=list(profile.esbmc_flags),
        notes=profile.notes,
        insertion_line=_parse_relative_line(finding),
        absolute_line=_parse_absolute_line(finding),
    )


def _assertion_property_from_expression(expression: str) -> str:
    expression = expression.strip()
    if not expression.startswith("assert "):
        return ""
    try:
        parsed = ast.parse(expression)
    except SyntaxError:
        return ""
    if len(parsed.body) != 1 or not isinstance(parsed.body[0], ast.Assert):
        return ""
    return ast.unparse(parsed.body[0].test).strip()


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
    if not isinstance(body.value, (ast.Name, ast.Attribute)):
        return "", ""
    if isinstance(body.slice, ast.Slice):
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
