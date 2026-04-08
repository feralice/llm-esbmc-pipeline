from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from typing import Protocol
from urllib import error, request

from .models import CodeUnit, Finding

FINDINGS_JSON_SCHEMA = {
    "name": "pipeline_findings",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "stage": {"type": "string"},
                        "finding_type": {"type": "string"},
                        "category": {"type": "string"},
                        "title": {"type": "string"},
                        "explanation": {"type": "string"},
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "verifiable": {"type": "boolean"},
                        "confidence": {"type": "string"},
                        "metadata": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "expression": {"type": "string"},
                                "line": {"type": "string"},
                                "relative_line": {"type": "string"},
                            },
                            "required": ["expression", "line", "relative_line"],
                        },
                    },
                    "required": [
                        "id",
                        "stage",
                        "finding_type",
                        "category",
                        "title",
                        "explanation",
                        "evidence",
                        "verifiable",
                        "confidence",
                        "metadata",
                    ],
                },
            }
        },
        "required": ["findings"],
    },
    "strict": True,
}


class LLMAnalyzer(Protocol):
    def analyze(self, unit: CodeUnit) -> list[Finding]:
        ...


class MockLLMAnalyzer:
    """Offline stand-in for LLM 1.

    The class uses deterministic heuristics so the rest of the pipeline can be
    executed without API credentials while preserving the same interfaces.
    """

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        findings: list[Finding] = []
        line_count = unit.metrics["line_count"]
        parameter_count = unit.metrics["parameter_count"]

        if line_count >= 20 or unit.metrics["branch_count"] >= 4:
            findings.append(
                Finding(
                    id=f"{unit.qualname}:long_method",
                    stage="llm_analysis",
                    finding_type="smell_heuristic",
                    category="long_method",
                    title="Long Method",
                    explanation=(
                        "A unidade concentra muitos ramos ou linhas, o que tende "
                        "a dificultar revisão, teste e manutenção."
                    ),
                    evidence=[
                        f"line_count={line_count}",
                        f"branch_count={unit.metrics['branch_count']}",
                    ],
                    verifiable=False,
                    confidence="medium",
                )
            )

        if parameter_count >= 6:
            findings.append(
                Finding(
                    id=f"{unit.qualname}:excessive_parameters",
                    stage="llm_analysis",
                    finding_type="smell_heuristic",
                    category="excessive_parameter_count",
                    title="Excessive Parameter Count",
                    explanation=(
                        "A funcao recebe muitos parametros, sinalizando possivel "
                        "baixa coesao ou concentracao excessiva de responsabilidade."
                    ),
                    evidence=[f"parameter_count={parameter_count}"],
                    verifiable=False,
                    confidence="medium",
                )
            )

        for op in unit.operations:
            if op.kind == "subscript":
                expression_suffix = _slugify(op.expression)
                findings.append(
                    Finding(
                        id=f"{unit.qualname}:subscript:{op.line}:{expression_suffix}",
                        stage="llm_analysis",
                        finding_type="suspected_bug",
                        category="out_of_bounds",
                        title="Possible Out-of-Bounds Access",
                        explanation=(
                            "Ha acesso indexado sem evidencias suficientes de que "
                            "o indice esteja sempre dentro dos limites da colecao."
                        ),
                        evidence=[f"line={op.line}", f"expression={op.expression}"],
                        verifiable=True,
                        confidence="medium",
                        metadata={
                            "expression": op.expression,
                            "line": str(op.line),
                            "relative_line": str(op.relative_line),
                        },
                    )
                )

            if op.kind == "division":
                expression_suffix = _slugify(op.expression)
                findings.append(
                    Finding(
                        id=f"{unit.qualname}:division:{op.line}:{expression_suffix}",
                        stage="llm_analysis",
                        finding_type="suspected_bug",
                        category="division_by_zero",
                        title="Possible Division by Zero",
                        explanation=(
                            "Existe operacao de divisao ou modulo que pode depender "
                            "de um denominador sem validacao explicita."
                        ),
                        evidence=[f"line={op.line}", f"expression={op.expression}"],
                        verifiable=True,
                        confidence="medium",
                        metadata={
                            "expression": op.expression,
                            "line": str(op.line),
                            "relative_line": str(op.relative_line),
                        },
                    )
                )

        if self._needs_validation_smell(unit):
            findings.append(
                Finding(
                    id=f"{unit.qualname}:input_validation",
                    stage="llm_analysis",
                    finding_type="smell_heuristic",
                    category="missing_input_validation",
                    title="Missing Input Validation",
                    explanation=(
                        "A unidade manipula operacoes sensiveis sem guardas claras "
                        "de pre-condicao, o que aumenta o risco de falhas."
                    ),
                    evidence=[
                        f"critical_operations={sum(1 for op in unit.operations if op.kind in {'subscript', 'division'})}",
                        f"guards={len(unit.guards)}",
                    ],
                    verifiable=False,
                    confidence="medium",
                )
            )

        return findings

    def _needs_validation_smell(self, unit: CodeUnit) -> bool:
        critical_ops = [op for op in unit.operations if op.kind in {"subscript", "division"}]
        return bool(critical_ops) and not unit.guards


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "expr"


class OpenAIResponsesAnalyzer:
    """Real LLM analyzer backed by the OpenAI Responses API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.4",
        base_url: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY nao configurada. Defina a variavel de ambiente ou passe api_key explicitamente."
            )

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Voce analisa codigo Python para um pipeline de pesquisa LLM + ESBMC. "
                                "Retorne apenas os dados estruturados solicitados, sem markdown, sem comentarios "
                                "e sem texto extra. A resposta deve ser um objeto com a chave 'findings', "
                                "contendo uma lista. "
                                "Cada finding precisa ter: "
                                "id, stage, finding_type, category, title, explanation, evidence, "
                                "verifiable, confidence e metadata. "
                                "Use finding_type='smell_heuristic' para smells e "
                                "finding_type='suspected_bug' para bugs ou vulnerabilidades suspeitas. "
                                "Marque verifiable=true apenas quando a suspeita puder virar uma propriedade "
                                "formal local do tipo divisao por zero ou acesso fora dos limites. "
                                "Use as categorias 'division_by_zero' e 'out_of_bounds' nesses casos. "
                                "Use stage='llm_analysis'. "
                                "Gere IDs unicos e estaveis por finding. "
                                "Evidencias devem ser curtas. Metadata deve sempre incluir as chaves "
                                "'expression', 'line' e 'relative_line'. Quando nao se aplicarem, use string vazia."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._build_user_prompt(unit),
                        }
                    ],
                },
            ],
            "text": {"format": {"type": "json_schema", **FINDINGS_JSON_SCHEMA}},
        }

        raw_response = self._post_json(payload)
        findings_data = self._extract_findings_payload(raw_response)
        findings = [self._finding_from_dict(item) for item in findings_data]
        return self._normalize_findings(unit, findings)

    def _build_user_prompt(self, unit: CodeUnit) -> str:
        operations = [asdict(op) for op in unit.operations]
        summary = {
            "path": str(unit.path),
            "name": unit.name,
            "qualname": unit.qualname,
            "start_line": unit.start_line,
            "end_line": unit.end_line,
            "parameters": unit.parameters,
            "type_hints": unit.type_hints,
            "loops": unit.loops,
            "conditionals": unit.conditionals,
            "guards": unit.guards,
            "metrics": unit.metrics,
            "operations": operations,
            "source": unit.source,
        }
        return (
            "Analise a unidade abaixo e gere findings uteis para um pipeline hibrido.\n"
            "Nao confunda code smell com bug.\n"
            "Se um acesso indexado ou divisao ja estiver protegido por guardas claros, evite falso positivo.\n"
            "Responda somente com JSON no schema pedido.\n\n"
            f"{json.dumps(summary, ensure_ascii=False, indent=2)}"
        )

    def _post_json(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.base_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Falha ao chamar OpenAI Responses API: {exc.code} {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Falha de rede ao chamar OpenAI Responses API: {exc.reason}") from exc

    def _extract_findings_payload(self, response_data: dict) -> list[dict]:
        if isinstance(response_data.get("output_text"), str):
            parsed = json.loads(response_data["output_text"])
            return self._coerce_findings(parsed)

        for item in response_data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parsed = json.loads(content["text"])
                    return self._coerce_findings(parsed)

        raise RuntimeError("A resposta da OpenAI nao contem texto JSON analisavel.")

    def _coerce_findings(self, payload: dict) -> list[dict]:
        findings = payload.get("findings")
        if not isinstance(findings, list):
            raise RuntimeError("JSON da LLM nao contem a chave 'findings' no formato esperado.")
        return findings

    def _finding_from_dict(self, data: dict) -> Finding:
        evidence_raw = data.get("evidence", [])
        if isinstance(evidence_raw, str):
            evidence = [evidence_raw]
        elif isinstance(evidence_raw, list):
            evidence = [str(item) for item in evidence_raw]
        else:
            evidence = [str(evidence_raw)]

        metadata_raw = data.get("metadata", {})
        if not isinstance(metadata_raw, dict):
            metadata_raw = {}
        metadata = {
            "expression": str(metadata_raw.get("expression", "")),
            "line": str(metadata_raw.get("line", "")),
            "relative_line": str(metadata_raw.get("relative_line", "")),
        }

        return Finding(
            id=str(data["id"]),
            stage=str(data["stage"]),
            finding_type=str(data["finding_type"]),
            category=str(data["category"]),
            title=str(data["title"]),
            explanation=str(data["explanation"]),
            evidence=evidence,
            verifiable=bool(data["verifiable"]),
            confidence=str(data["confidence"]),
            metadata=metadata,
        )

    def _normalize_findings(self, unit: CodeUnit, findings: list[Finding]) -> list[Finding]:
        normalized: list[Finding] = []
        seen_ids: set[str] = set()
        for index, finding in enumerate(findings, start=1):
            metadata = dict(finding.metadata)
            if finding.verifiable:
                expression = metadata.get("expression", "")
                if expression and "relative_line" not in metadata:
                    matched_op = next(
                        (
                            op
                            for op in unit.operations
                            if op.expression == expression
                            and (
                                (finding.category == "division_by_zero" and op.kind == "division")
                                or (finding.category == "out_of_bounds" and op.kind == "subscript")
                            )
                        ),
                        None,
                    )
                    if matched_op is not None:
                        metadata["line"] = str(matched_op.line)
                        metadata["relative_line"] = str(matched_op.relative_line)
            candidate_id = finding.id.strip() or f"{unit.qualname}:llm:{index}"
            if candidate_id in seen_ids:
                candidate_id = f"{candidate_id}:{index}"
            seen_ids.add(candidate_id)
            normalized.append(
                Finding(
                    id=candidate_id,
                    stage=finding.stage or "llm_analysis",
                    finding_type=finding.finding_type,
                    category=finding.category,
                    title=finding.title,
                    explanation=finding.explanation,
                    evidence=finding.evidence,
                    verifiable=finding.verifiable,
                    confidence=finding.confidence,
                    metadata=metadata,
                )
            )
        return normalized
