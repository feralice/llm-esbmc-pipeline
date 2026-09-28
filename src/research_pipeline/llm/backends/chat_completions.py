from __future__ import annotations

import json
import logging
import time
from urllib import error, request

logger = logging.getLogger(__name__)

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
    stage_schema,
)
from ..rate_limit import is_daily_quota_exhausted
from ..telemetry import response_event


class ChatCompletionsAnalyzer:
    """Analyzer para APIs compatíveis com OpenAI Chat Completions."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "deepseek-r1:7b",
        api_key: str = "ollama",
        timeout_seconds: int = 300,
        request_delay: float = 0.0,
        include_smells: bool = True,
        v2_categories: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.request_delay = request_delay
        self.include_smells = include_smells
        self.v2_categories = v2_categories
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        if self.request_delay > 0:
            time.sleep(self.request_delay)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": load_system_prompt(include_smells=self.include_smells, v2_categories=self.v2_categories)},
                {"role": "user", "content": build_user_prompt(unit, include_smells=self.include_smells, v2_categories=self.v2_categories)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        }
        started = time.monotonic()
        try:
            raw_response = self._post_json(payload)
        except Exception as exc:
            self.telemetry_events.append(response_event(
                provider="chat_completions", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            ))
            raise
        self.telemetry_events.append(response_event(
            provider="chat_completions", requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=raw_response,
        ))
        findings_data = self._extract_findings_payload(raw_response)
        findings = [finding_from_dict(item) for item in findings_data]
        return normalize_findings(unit, findings)

    def analyze_stage(self, unit, *, stage, candidates=None):
        if self.request_delay > 0:
            time.sleep(self.request_delay)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": build_stage_system_prompt(stage)},
                {"role": "user", "content": build_stage_user_prompt(unit, stage=stage, candidates=candidates)},
            ],
            "response_format": {"type": "json_schema", "json_schema": stage_schema(stage)},
            "temperature": 0,
            "stream": False,
        }
        started = time.monotonic()
        try:
            raw_response = self._post_json(payload)
            result = parse_stage_payload(
                self._extract_json_payload(raw_response), stage=stage, candidates=candidates,
            )
        except Exception as exc:
            event = response_event(
                provider="chat_completions", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            )
            event["analysis_stage"] = stage
            self.telemetry_events.append(event)
            raise
        event = response_event(
            provider="chat_completions", requested_model=self.model,
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
                    raise RuntimeError(f"Falha ao chamar API Chat Completions: {exc.code} {details}") from exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < _retries - 1:
                    sleep_time = 45 if exc.code == 429 else 2 ** (attempt + 2)
                    time.sleep(sleep_time)
                    continue
                raise RuntimeError(f"Falha ao chamar API Chat Completions: {exc.code} {details}") from exc
            except TimeoutError as exc:
                if attempt < _retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(
                    f"Timeout ({self.timeout_seconds}s) ao chamar {self.base_url}. "
                    "Aumente --llm-timeout ou verifique se Ollama está respondendo."
                ) from exc
            except error.URLError as exc:
                hint = (
                    "\nVerifique se o Ollama está rodando com: ollama serve"
                    if "localhost" in self.base_url or "127.0.0.1" in self.base_url
                    else ""
                )
                raise RuntimeError(
                    f"Falha de rede ao chamar {self.base_url}: {exc.reason}{hint}"
                ) from exc
        raise RuntimeError("API Chat Completions falhou após todas as tentativas.")

    def _extract_findings_payload(self, response_data: dict) -> list[dict]:
        choices = response_data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                try:
                    return coerce_findings_payload(
                        json.loads(strip_markdown_json(content))
                    )
                except (json.JSONDecodeError, RuntimeError) as exc:
                    logger.warning(
                        "JSON parse failed for model %s: %s | raw: %.200s",
                        self.model, exc, content,
                    )
                    return []
        return []

    def _extract_json_payload(self, response_data: dict) -> dict:
        choices = response_data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                try:
                    return json.loads(strip_markdown_json(content))
                except (json.JSONDecodeError, RuntimeError) as exc:
                    logger.warning("JSON parse failed for model %s: %s | raw: %.200s", self.model, exc, content)
                    raise RuntimeError("Resposta staged sem JSON válido") from exc
        return []
