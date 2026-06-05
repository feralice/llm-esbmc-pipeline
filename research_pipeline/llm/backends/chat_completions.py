from __future__ import annotations

import json
from urllib import error, request

from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings, strip_markdown_json
from ..prompts import build_user_prompt, load_system_prompt
from ...models import CodeUnit, Finding


class ChatCompletionsAnalyzer:
    """Analyzer para APIs compatíveis com OpenAI Chat Completions."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/api/generate",
        model: str = "qwen2.5-coder:7b",
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
                {"role": "system", "content": load_system_prompt()},
                {"role": "user", "content": build_user_prompt(unit)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }
        raw_response = self._post_json(payload)
        findings_data = self._extract_findings_payload(raw_response)
        findings = [finding_from_dict(item) for item in findings_data]
        return normalize_findings(unit, findings)

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
                parsed = json.loads(strip_markdown_json(content))
                return coerce_findings_payload(parsed)
        raise RuntimeError("Resposta da API não contém conteúdo JSON analisável.")
