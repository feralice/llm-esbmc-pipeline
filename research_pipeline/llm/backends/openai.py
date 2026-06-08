from __future__ import annotations

import json
import os
import time
from urllib import error, request

from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings
from ..prompts import PromptMode, build_user_prompt, load_system_prompt
from ..schema import FINDINGS_JSON_SCHEMA
from ...models import CodeUnit, Finding


class OpenAIResponsesAnalyzer:
    """LLM analyzer backed by the OpenAI Responses API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 60,
        prompt_mode: PromptMode = "raw",
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.prompt_mode = prompt_mode
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY não configurada. Defina a variável de ambiente ou passe api_key."
            )

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": load_system_prompt()}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": build_user_prompt(unit, self.prompt_mode)}],
                },
            ],
            "text": {"format": {"type": "json_schema", **FINDINGS_JSON_SCHEMA}},
        }

        raw_response = self._post_json(payload)
        findings_data = self._extract_findings_payload(raw_response)
        findings = [finding_from_dict(item) for item in findings_data]
        return normalize_findings(unit, findings)

    def _post_json(self, payload: dict, _retries: int = 3) -> dict:
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(_retries):
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
                if exc.code in (429, 500, 502, 503, 504) and attempt < _retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                details = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Falha ao chamar OpenAI Responses API: {exc.code} {details}") from exc
            except error.URLError as exc:
                if attempt < _retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Falha de rede ao chamar OpenAI Responses API: {exc.reason}") from exc
            except TimeoutError as exc:
                if attempt < _retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError("Timeout ao chamar OpenAI Responses API.") from exc
        raise RuntimeError("OpenAI API falhou após todas as tentativas de retry.")

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
