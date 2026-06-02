from __future__ import annotations

import json
import os
from urllib import error, request

from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings, strip_markdown_json
from ..prompts import build_user_prompt, load_system_prompt
from ...models import CodeUnit, Finding


class AnthropicAnalyzer:
    """LLM analyzer backed by the Anthropic Messages API."""

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
            "system": load_system_prompt(),
            "messages": [
                {"role": "user", "content": build_user_prompt(unit)},
            ],
        }

        raw_response = self._post_json(payload)
        findings_data = self._extract_findings_payload(raw_response)
        findings = [finding_from_dict(item) for item in findings_data]
        return normalize_findings(unit, findings)

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
                parsed = json.loads(strip_markdown_json(block["text"]))
                return coerce_findings_payload(parsed)
        raise RuntimeError("A resposta da Anthropic não contém texto JSON analisável.")
