from __future__ import annotations

import json
import os
import time
from urllib import error, request

from ...models import CodeUnit, Finding
from ..findings import (
    coerce_findings_payload,
    finding_from_dict,
    normalize_findings,
    strip_markdown_json,
)
from ..prompts import build_user_prompt, load_system_prompt
from ..staged import (
    build_stage_system_prompt,
    build_stage_user_prompt,
    parse_stage_payload,
)
from ..telemetry import response_event


class AnthropicAnalyzer:
    """LLM analyzer backed by the Anthropic Messages API."""

    _API_URL = "https://api.anthropic.com/v1/messages"
    _API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-opus-4-8",
        timeout_seconds: int = 60,
        include_smells: bool = True,
        v2_categories: bool = False,
    ) -> None:
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.include_smells = include_smells
        self.v2_categories = v2_categories
        if not resolved_key:
            raise ValueError(
                "ANTHROPIC_API_KEY não configurada. Defina a variável de ambiente ou passe api_key."
            )
        self.api_key: str = resolved_key
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": load_system_prompt(include_smells=self.include_smells, v2_categories=self.v2_categories),
            "messages": [
                {"role": "user", "content": build_user_prompt(unit, include_smells=self.include_smells, v2_categories=self.v2_categories)},
            ],
        }

        started = time.monotonic()
        try:
            raw_response = self._post_json(payload)
        except Exception as exc:
            self.telemetry_events.append(response_event(
                provider="anthropic", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            ))
            raise
        self.telemetry_events.append(response_event(
            provider="anthropic", requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=raw_response,
        ))
        findings_data = self._extract_findings_payload(raw_response)
        findings = [finding_from_dict(item) for item in findings_data]
        return normalize_findings(unit, findings)

    def analyze_stage(self, unit, *, stage, candidates=None):
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": build_stage_system_prompt(stage),
            "messages": [
                {"role": "user", "content": build_stage_user_prompt(unit, stage=stage, candidates=candidates)},
            ],
        }
        started = time.monotonic()
        try:
            raw_response = self._post_json(payload)
            result = parse_stage_payload(
                self._extract_json_payload(raw_response), stage=stage, candidates=candidates,
            )
        except Exception as exc:
            event = response_event(
                provider="anthropic", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            )
            event["analysis_stage"] = stage
            self.telemetry_events.append(event)
            raise
        event = response_event(
            provider="anthropic", requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=raw_response,
        )
        event["analysis_stage"] = stage
        self.telemetry_events.append(event)
        return result

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
        return coerce_findings_payload(self._extract_json_payload(response_data))

    def _extract_json_payload(self, response_data: dict) -> dict:
        for block in response_data.get("content", []):
            if block.get("type") == "text":
                return json.loads(strip_markdown_json(block["text"]))
        raise RuntimeError("A resposta da Anthropic não contém texto JSON analisável.")
