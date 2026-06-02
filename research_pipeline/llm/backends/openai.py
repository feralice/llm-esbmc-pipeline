from __future__ import annotations

import json
import os
from urllib import error, request

from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings
from ..prompts import FINDINGS_JSON_SCHEMA, build_user_prompt, load_system_prompt
from ...models import CodeUnit, Finding


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
                    "content": [{"type": "input_text", "text": load_system_prompt()}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": build_user_prompt(unit)}],
                },
            ],
            "text": {"format": {"type": "json_schema", **FINDINGS_JSON_SCHEMA}},
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
            raise RuntimeError(f"Falha ao chamar OpenAI Responses API: {exc.code} {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Falha de rede ao chamar OpenAI Responses API: {exc.reason}") from exc

    def _extract_findings_payload(self, response_data: dict) -> list[dict]:
        if isinstance(response_data.get("output_text"), str):
            parsed = json.loads(response_data["output_text"])
            return coerce_findings_payload(parsed)

        for item in response_data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parsed = json.loads(content["text"])
                    return coerce_findings_payload(parsed)

        raise RuntimeError("A resposta da OpenAI não contém texto JSON analisável.")
