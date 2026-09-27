from __future__ import annotations

import json
import os
import time
from urllib import error, request

from ...models import CodeUnit, Finding
from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings
from ..prompts import build_user_prompt, load_system_prompt
from ..staged import (
    build_stage_system_prompt,
    build_stage_user_prompt,
    parse_stage_payload,
    stage_schema,
)
from ..rate_limit import is_daily_quota_exhausted
from ..schema import FINDINGS_JSON_SCHEMA
from ..telemetry import response_event


class OpenAIResponsesAnalyzer:
    """LLM analyzer backed by the OpenAI Responses API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.5",
        base_url: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 60,
        include_smells: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.include_smells = include_smells
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY não configurada. Defina a variável de ambiente ou passe api_key."
            )
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": load_system_prompt(include_smells=self.include_smells)}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": build_user_prompt(unit, include_smells=self.include_smells)}],
                },
            ],
            "text": {"format": {"type": "json_schema", **FINDINGS_JSON_SCHEMA}},
        }

        started = time.monotonic()
        try:
            raw_response = self._post_json(payload)
        except Exception as exc:
            self.telemetry_events.append(response_event(
                provider="openai", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            ))
            raise
        self.telemetry_events.append(response_event(
            provider="openai", requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=raw_response,
        ))
        findings_data = self._extract_findings_payload(raw_response)
        findings = [finding_from_dict(item) for item in findings_data]
        return normalize_findings(unit, findings)

    def analyze_stage(self, unit, *, stage, candidates=None):
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": build_stage_system_prompt(stage)}]},
                {"role": "user", "content": [{"type": "input_text", "text": build_stage_user_prompt(unit, stage=stage, candidates=candidates)}]},
            ],
            "text": {"format": {"type": "json_schema", **stage_schema(stage)}},
        }
        started = time.monotonic()
        try:
            raw_response = self._post_json(payload)
            result = parse_stage_payload(
                self._extract_json_payload(raw_response), stage=stage, candidates=candidates,
            )
        except Exception as exc:
            event = response_event(
                provider="openai", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            )
            event["analysis_stage"] = stage
            self.telemetry_events.append(event)
            raise
        event = response_event(
            provider="openai", requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=raw_response,
        )
        event["analysis_stage"] = stage
        self.telemetry_events.append(event)
        return result

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
                details = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and is_daily_quota_exhausted(details):
                    raise RuntimeError(f"Falha ao chamar OpenAI Responses API: {exc.code} {details}") from exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < _retries - 1:
                    time.sleep(2 ** attempt)
                    continue
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
        return coerce_findings_payload(self._extract_json_payload(response_data))

    def _extract_json_payload(self, response_data: dict) -> dict:
        if isinstance(response_data.get("output_text"), str):
            return json.loads(response_data["output_text"])

        for item in response_data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return json.loads(content["text"])

        raise RuntimeError("A resposta da OpenAI não contém texto JSON analisável.")
