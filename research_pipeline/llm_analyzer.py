from __future__ import annotations

import json
import os
from typing import Protocol
from urllib import error, request

from .models import CodeUnit, Finding

# ---------------------------------------------------------------------------
# Shared prompt content
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "Você é um analisador estático especializado em Python para um pipeline híbrido de pesquisa LLM + ESBMC.\n\n"

    "Sua tarefa: analisar funções Python e gerar achados estruturados em dois tipos:\n"
    "  1. TRILHA HEURÍSTICA (smell_heuristic): problemas de qualidade que NÃO podem ser verificados formalmente.\n"
    "  2. TRILHA FORMAL (suspected_bug): erros de runtime que PODEM ser verificados pelo ESBMC "
    "via bounded model checking.\n\n"

    "## REGRAS DA TRILHA FORMAL\n"
    "Marque verifiable=true SOMENTE para:\n"
    "  - category='division_by_zero': divisão (/, //, %) com divisor VARIÁVEL que pode ser zero.\n"
    "  - category='out_of_bounds': acesso indexado (lista[idx]) com índice VARIÁVEL que pode estar fora do intervalo.\n\n"
    "NÃO marque verifiable=true quando:\n"
    "  - O divisor ou índice é uma constante literal: x/2, arr[0], lst[-1], x%3.\n"
    "  - Há guarda clara ANTES da operação: 'if denom != 0:', 'assert idx < len(arr)', 'if not items:', etc.\n"
    "  - A variável foi validada por condicional ou assert antes do ponto suspeito.\n"
    "  - O acesso é um slice com literais: lst[::-1], lst[1:3].\n\n"

    "## CATEGORIAS DA TRILHA HEURÍSTICA\n"
    "Use uma dessas categorias para achados smell_heuristic:\n"
    "  - long_method: função com mais de 20 linhas\n"
    "  - complex_conditional: muitos ramos ou condicionais aninhados (branch_count > 3)\n"
    "  - many_parameters: mais de 4 parâmetros\n"
    "  - missing_validation: parâmetros sem type hints ou sem validação de entrada\n"
    "  - magic_number: valores numéricos hardcoded sem nome explicativo\n"
    "  - poor_naming: nomes de variáveis ou parâmetros pouco claros (a, b, x, tmp, etc.)\n\n"

    "## NÍVEIS DE CONFIANÇA\n"
    "  - high: evidência forte, impacto claro, sem ambiguidade\n"
    "  - medium: possível problema, depende do contexto de chamada\n"
    "  - low: especulativo, improvável de causar problema real\n\n"

    "## EXEMPLOS DE ACHADOS CORRETOS\n\n"

    "### CASO 1 — division_by_zero real (verifiable=true)\n"
    "Código: def calc(x: int, n: int) -> int: return x // n\n"
    "Correto: verifiable=true, category='division_by_zero', expression='x // n', confidence='high'\n"
    "Motivo: 'n' é variável sem guarda — pode ser zero.\n\n"

    "### CASO 2 — divisor literal (verifiable=false)\n"
    "Código: def half(x: int) -> float: return x / 2\n"
    "Correto: verifiable=false — '2' é literal, nunca será zero. Não gere finding formal.\n\n"

    "### CASO 3 — out_of_bounds real (verifiable=true)\n"
    "Código: def get(lst: List[int], i: int) -> int: return lst[i]\n"
    "Correto: verifiable=true, category='out_of_bounds', expression='lst[i]', confidence='high'\n"
    "Motivo: 'i' é variável sem restrição de intervalo.\n\n"

    "### CASO 4 — operação protegida por guarda (verifiable=false)\n"
    "Código: def safe(lst, i): return lst[i] if 0 <= i < len(lst) else None\n"
    "Correto: verifiable=false — a guarda 'if 0 <= i < len(lst)' protege o acesso.\n\n"

    "### CASO 5 — smell sem bug formal\n"
    "Código: def f(a, b, c, d, e): ...\n"
    "Correto: finding_type='smell_heuristic', category='many_parameters', verifiable=false\n\n"

    "### CASO 6 — código limpo, sem achados\n"
    "Código: def add(a: int, b: int) -> int: return a + b\n"
    "Correto: {\"findings\": []}  — retorne lista vazia.\n\n"

    "## REGRAS DE SAÍDA\n"
    "  - Retorne APENAS o objeto JSON com a chave 'findings'. Sem markdown, sem comentários.\n"
    "  - evidence: snippets CURTOS do código real (máximo 1 linha por item).\n"
    "  - explanation: clara e objetiva (2-4 frases sobre o risco ou problema).\n"
    "  - IDs únicos, ex: analyze_me_division_by_zero_1\n"
    "  - metadata.expression: expressão exata (ex: 'lst[i]', 'x // n').\n"
    "  - metadata.line: linha absoluta no arquivo.\n"
    "  - metadata.relative_line: linha relativa ao início da função (1 = primeira linha).\n"
    "  - Se não houver problemas: {\"findings\": []}.\n"
)

_FINDINGS_JSON_SCHEMA = {
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


def _build_user_prompt(unit: CodeUnit) -> str:
    divisions = [op for op in unit.operations if op.kind == "division"]
    subscripts = [op for op in unit.operations if op.kind == "subscript"]

    def fmt_ops(ops: list) -> str:
        if not ops:
            return "  (nenhuma)"
        return "\n".join(f"  - linha relativa {op.relative_line}: {op.expression}" for op in ops)

    guards_str = (
        "\n".join(f"  - {g}" for g in unit.guards)
        if unit.guards
        else "  (nenhuma guarda detectada)"
    )

    metadata = {
        "path": str(unit.path),
        "start_line": unit.start_line,
        "end_line": unit.end_line,
        "parameters": unit.parameters,
        "type_hints": unit.type_hints,
        "metrics": unit.metrics,
    }

    return (
        f"Analise a função '{unit.qualname}' para o pipeline LLM + ESBMC.\n\n"
        "OPERAÇÕES DETECTADAS PELA ANÁLISE ESTÁTICA:\n"
        f"  Divisões/módulos (/, //, %):\n{fmt_ops(divisions)}\n"
        f"  Acessos indexados (subscripts):\n{fmt_ops(subscripts)}\n\n"
        f"GUARDAS/ASSERTS EXISTENTES:\n{guards_str}\n\n"
        "CÓDIGO DA FUNÇÃO:\n"
        f"```python\n{unit.source}\n```\n\n"
        "METADADOS DA FUNÇÃO:\n"
        f"{json.dumps(metadata, ensure_ascii=False, indent=2)}\n\n"
        "Instruções:\n"
        "1. Revise cada operação detectada para riscos de runtime (division_by_zero, out_of_bounds).\n"
        "2. Se guardas existentes já protegem a operação, NÃO reporte como verifiable=true.\n"
        "3. Identifique smells de qualidade de código presentes.\n"
        "4. Para cada achado: explanation clara e evidence com trecho real do código.\n\n"
        "Responda SOMENTE com JSON válido no schema solicitado."
    )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class LLMAnalyzer(Protocol):
    def analyze(self, unit: CodeUnit) -> list[Finding]: ...


# ---------------------------------------------------------------------------
# Shared parsing logic
# ---------------------------------------------------------------------------


def _coerce_findings(payload: dict) -> list[dict]:
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise RuntimeError("JSON da LLM não contém a chave 'findings' no formato esperado.")
    return findings


def _finding_from_dict(data: dict) -> Finding:
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


_VERIFIABLE_OP_KIND: dict[str, str] = {
    "division_by_zero": "division",
    "out_of_bounds": "subscript",
}


def _normalize_findings(unit: CodeUnit, findings: list[Finding]) -> list[Finding]:
    normalized: list[Finding] = []
    seen_ids: set[str] = set()
    for index, finding in enumerate(findings, start=1):
        metadata = dict(finding.metadata)
        verifiable = finding.verifiable
        finding_type = finding.finding_type

        if verifiable:
            expected_op_kind = _VERIFIABLE_OP_KIND.get(finding.category)
            if expected_op_kind is None:
                # LLM marcou verifiable em categoria que não tem verificação formal — rebaixa
                verifiable = False
                finding_type = "smell_heuristic"
            else:
                expression = metadata.get("expression", "")
                matched_op = next(
                    (
                        op
                        for op in unit.operations
                        if op.kind == expected_op_kind
                        and (not expression or op.expression == expression)
                    ),
                    None,
                )
                if matched_op is not None:
                    metadata["line"] = str(matched_op.line)
                    metadata["relative_line"] = str(matched_op.relative_line)
                else:
                    # LLM alucinou: disse verifiable mas não há operação correspondente
                    verifiable = False
                    finding_type = "smell_heuristic"

        candidate_id = finding.id.strip() or f"{unit.qualname}:llm:{index}"
        if candidate_id in seen_ids:
            candidate_id = f"{candidate_id}:{index}"
        seen_ids.add(candidate_id)
        normalized.append(
            Finding(
                id=candidate_id,
                stage=finding.stage or "llm_analysis",
                finding_type=finding_type,
                category=finding.category,
                title=finding.title,
                explanation=finding.explanation,
                evidence=finding.evidence,
                verifiable=verifiable,
                confidence=finding.confidence,
                metadata=metadata,
            )
        )
    return normalized


def _strip_markdown_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening fence (```json or ```)
        lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------


class OpenAIResponsesAnalyzer:
    """LLM analyzer backed by the OpenAI Responses API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY não configurada. Defina a variável de ambiente ou passe api_key."
            )

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": _SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": _build_user_prompt(unit)}],
                },
            ],
            "text": {"format": {"type": "json_schema", **_FINDINGS_JSON_SCHEMA}},
        }

        raw_response = self._post_json(payload)
        findings_data = self._extract_findings_payload(raw_response)
        findings = [_finding_from_dict(item) for item in findings_data]
        return _normalize_findings(unit, findings)

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
            return _coerce_findings(parsed)

        for item in response_data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parsed = json.loads(content["text"])
                    return _coerce_findings(parsed)

        raise RuntimeError("A resposta da OpenAI não contém texto JSON analisável.")


# ---------------------------------------------------------------------------
# Anthropic (Claude) backend
# ---------------------------------------------------------------------------


class AnthropicAnalyzer:
    """LLM analyzer backed by the Anthropic Messages API (Claude)."""

    _API_URL = "https://api.anthropic.com/v1/messages"
    _API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.timeout_seconds = timeout_seconds
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY não configurada. Defina a variável de ambiente ou passe api_key."
            )

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": _build_user_prompt(unit)},
            ],
        }

        raw_response = self._post_json(payload)
        findings_data = self._extract_findings_payload(raw_response)
        findings = [_finding_from_dict(item) for item in findings_data]
        return _normalize_findings(unit, findings)

    def _post_json(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self._API_URL,
            data=body,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self._API_VERSION,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Falha ao chamar Anthropic API: {exc.code} {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Falha de rede ao chamar Anthropic API: {exc.reason}") from exc

    def _extract_findings_payload(self, response_data: dict) -> list[dict]:
        for block in response_data.get("content", []):
            if block.get("type") == "text":
                text = _strip_markdown_json(block["text"])
                parsed = json.loads(text)
                return _coerce_findings(parsed)
        raise RuntimeError("A resposta da Anthropic não contém texto JSON analisável.")
