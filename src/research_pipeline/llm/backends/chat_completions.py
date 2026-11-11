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
from ..rate_limit import UsageLimitReached, call_failure, is_daily_quota_exhausted
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
        v2_detection: bool = False,
        v2_variants: tuple[str, ...] = (),
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.request_delay = request_delay
        self.include_smells = include_smells
        self.v2_detection = v2_detection
        self.v2_variants = v2_variants
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        if self.request_delay > 0:
            time.sleep(self.request_delay)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": load_system_prompt(include_smells=self.include_smells, v2_detection=self.v2_detection, v2_variants=self.v2_variants)},
                {"role": "user", "content": build_user_prompt(unit, include_smells=self.include_smells, v2_variants=self.v2_variants)},
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
        return normalize_findings(unit, findings, v2_detection=self.v2_detection)


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
                    raise UsageLimitReached(f"Falha ao chamar API Chat Completions: {exc.code} {details}") from exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < _retries - 1:
                    sleep_time = 45 if exc.code == 429 else 2 ** (attempt + 2)
                    time.sleep(sleep_time)
                    continue
                raise call_failure(f"Falha ao chamar API Chat Completions: {exc.code} {details}", details) from exc
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
        payload = self._extract_json_payload(response_data)
        try:
            findings = coerce_findings_payload(payload)
        except (TypeError, RuntimeError) as exc:
            raise RuntimeError("Resposta JSON sem findings válidos") from exc
        if not all(isinstance(item, dict) for item in findings):
            raise RuntimeError("Resposta JSON contém findings que não são objetos")
        return findings

    def _extract_json_payload(self, response_data: dict) -> dict:
        try:
            content = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("A resposta não contém conteúdo JSON analisável") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("A resposta não contém conteúdo JSON analisável")
        try:
            payload = json.loads(strip_markdown_json(content))
        except (json.JSONDecodeError, RuntimeError) as exc:
            logger.warning("JSON parse failed for model %s: %s", self.model, exc)
            raise RuntimeError("Resposta sem JSON válido") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("A resposta JSON deve ser um objeto")
        return payload
