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
    "  1. TRILHA FORMAL (suspected_bug, verifiable=true): erros de runtime que PODEM causar exceção "
    "e que o ESBMC pode verificar formalmente via bounded model checking.\n"
    "  2. TRILHA HEURÍSTICA (smell_heuristic, verifiable=false): problemas de qualidade de código "
    "que prejudicam legibilidade ou manutenção, mas não causam exceção diretamente.\n\n"

    "## O QUE É UM BUG FORMAL\n\n"

    "### division_by_zero\n"
    "Acontece quando o Python executa uma divisão (/, //, %) e o denominador vale zero em tempo de execução. "
    "Isso lança ZeroDivisionError e encerra o programa abruptamente.\n"
    "Um bug é real quando o denominador é uma VARIÁVEL ou expressão que PODE assumir zero "
    "e não há nada no código que garanta que ele nunca será zero antes da divisão.\n"
    "Pergunta-chave: 'Existe algum valor dos parâmetros que faria o denominador ser zero?' "
    "Se sim, e não há guarda, marque verifiable=true.\n\n"

    "### out_of_bounds\n"
    "Acontece quando o Python acessa lst[i] e o índice i está fora do intervalo válido "
    "[0, len(lst)-1]. Isso lança IndexError.\n"
    "Um bug é real quando o índice é uma VARIÁVEL que pode ser negativo, maior ou igual ao tamanho "
    "da lista, e não há verificação prévia que garanta que o acesso é seguro.\n"
    "Pergunta-chave: 'Existe algum valor dos parâmetros que faria o índice cair fora da lista?' "
    "Se sim, e não há guarda, marque verifiable=true.\n\n"

    "## QUANDO NÃO MARCAR verifiable=true\n"
    "  - O divisor ou índice é uma constante literal: x/2, arr[0], lst[-1], x%3.\n"
    "  - Há verificação ANTES da operação: 'if denom != 0:', 'if 0 <= i < len(lst):', "
    "'assert idx < len(arr)', 'if not items:', etc.\n"
    "  - O acesso é um slice com literais: lst[::-1], lst[1:3].\n\n"

    "## O QUE SÃO SMELLS DE CÓDIGO\n"
    "Smells não causam exceção mas indicam problemas de design ou legibilidade. "
    "Analise a função como um todo e reporte o que realmente está presente:\n"
    "  - long_method: função excessivamente longa, difícil de entender de uma vez\n"
    "  - complex_conditional: lógica condicional com muitos ramos, aninhamentos ou condições compostas\n"
    "  - many_parameters: lista de parâmetros longa, indica que a função faz coisas demais\n"
    "  - missing_validation: parâmetros sem type hints e sem qualquer verificação de entrada\n"
    "  - magic_number: valores numéricos sem nome ou contexto que explique seu significado\n"
    "  - poor_naming: nomes de 1 letra (a, b, x, n), abreviações obscuras ou genéricos (tmp, val, data, res)\n\n"

    "## NÍVEIS DE CONFIANÇA\n"
    "  - high: a evidência no código é clara e direta, sem ambiguidade\n"
    "  - medium: possível problema, mas depende do contexto de uso\n"
    "  - low: especulativo ou improvável de causar problema real\n\n"

    "## EXEMPLOS\n\n"

    "### CASO 1 — division_by_zero (verifiable=true)\n"
    "Código: def calc(x: int, n: int) -> int: return x // n\n"
    "Análise: 'n' é parâmetro livre — se o chamador passar 0, o programa quebra com ZeroDivisionError. "
    "Não há nenhuma verificação antes da divisão.\n"
    "Resultado: verifiable=true, category='division_by_zero', confidence='high'\n\n"

    "### CASO 2 — divisor literal (sem finding formal)\n"
    "Código: def half(x: int) -> float: return x / 2\n"
    "Análise: o denominador é 2, uma constante. Nunca será zero.\n"
    "Resultado: não gere finding formal para essa divisão.\n\n"

    "### CASO 3 — out_of_bounds (verifiable=true)\n"
    "Código: def get(lst: List[int], i: int) -> int: return lst[i]\n"
    "Análise: 'i' é parâmetro livre sem restrição. Se i >= len(lst) ou i < 0, lança IndexError. "
    "Não há guarda alguma.\n"
    "Resultado: verifiable=true, category='out_of_bounds', confidence='high'\n\n"

    "### CASO 4 — acesso protegido por guarda (verifiable=false)\n"
    "Código: def safe(lst, i): return lst[i] if 0 <= i < len(lst) else None\n"
    "Análise: a expressão condicional garante que o acesso só ocorre quando i está dentro dos limites.\n"
    "Resultado: verifiable=false — não há risco real.\n\n"

    "### CASO 5 — função com múltiplos smells\n"
    "Código: def proc(a, b, c, d, e, f):\n"
    "            x = a + b\n"
    "            if x > 0:\n"
    "                if c > 0: x += c\n"
    "                else: x -= c\n"
    "            elif b < 0: x += d + e + f\n"
    "            return x\n"
    "Análise: seis parâmetros (lista longa), if aninhado dentro de if/elif (lógica complexa), "
    "todos os nomes são letras únicas (péssima legibilidade).\n"
    "Resultado: three findings — many_parameters, complex_conditional, poor_naming. Todos verifiable=false.\n\n"

    "### CASO 6 — código limpo\n"
    "Código: def add(a: int, b: int) -> int: return a + b\n"
    "Análise: operação simples, sem divisão, sem acesso indexado, sem smells relevantes.\n"
    "Resultado: {\"findings\": []} — lista vazia.\n\n"

    "## REGRAS DE SAÍDA\n"
    "  - Retorne APENAS o objeto JSON com a chave 'findings'. Sem markdown, sem comentários.\n"
    "  - evidence: trecho EXATO do código (máximo 1 linha por item).\n"
    "  - explanation: 2-4 frases explicando o risco concreto ou o problema de qualidade.\n"
    "  - IDs únicos no formato: nomefuncao_categoria_N (ex: get_out_of_bounds_1).\n"
    "  - metadata.expression: expressão exata envolvida (ex: 'lst[i]', 'x // n').\n"
    "  - metadata.line: linha absoluta no arquivo.\n"
    "  - metadata.relative_line: linha relativa ao início da função (1 = primeira linha da função).\n"
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
        id=str(data.get("id") or "unknown"),
        stage=str(data.get("stage") or "llm_analysis"),
        finding_type=str(data.get("finding_type") or "smell_heuristic"),
        category=str(data.get("category") or "unknown"),
        title=str(data.get("title") or ""),
        explanation=str(data.get("explanation") or ""),
        evidence=evidence,
        verifiable=bool(data.get("verifiable", False)),
        confidence=str(data.get("confidence") or "low"),
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
                    finding_type = "suspected_bug"
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
# Chat Completions backend (Ollama, LM Studio, qualquer OpenAI-compatible)
# ---------------------------------------------------------------------------


class ChatCompletionsAnalyzer:
    """Analyzer para qualquer API compatível com OpenAI Chat Completions (Ollama, LM Studio, etc.)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3.2",
        api_key: str = "ollama",
        timeout_seconds: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(unit)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
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
            raise RuntimeError(f"Falha ao chamar API Chat Completions: {exc.code} {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"Falha de rede ao chamar {self.base_url}: {exc.reason}\n"
                "Verifique se o Ollama está rodando com: ollama serve"
            ) from exc

    def _extract_findings_payload(self, response_data: dict) -> list[dict]:
        choices = response_data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                text = _strip_markdown_json(content)
                parsed = json.loads(text)
                return _coerce_findings(parsed)
        raise RuntimeError("Resposta da API não contém conteúdo JSON analisável.")


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
