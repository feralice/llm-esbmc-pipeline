from __future__ import annotations

import json
import logging
import time
from urllib import error, request

logger = logging.getLogger(__name__)

from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings, strip_markdown_json
from ..prompts import build_user_prompt, load_system_prompt
from ...models import CodeUnit, Finding
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
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.request_delay = request_delay
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        if self.request_delay > 0:
            time.sleep(self.request_delay)
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
                    sleep_time = 45 if exc.code == 429 else 2 ** (attempt + 2)
                    time.sleep(sleep_time)
                    continue
                details = exc.read().decode("utf-8", errors="replace")
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
                raise RuntimeError(
                    f"Falha de rede ao chamar {self.base_url}: {exc.reason}\n"
                    "Verifique se o Ollama está rodando com: ollama serve"
                ) from exc
        raise RuntimeError("API Chat Completions falhou após todas as tentativas.")

    def _extract_findings_payload(self, response_data: dict) -> list[dict]:
        choices = response_data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                try:
                    parsed = json.loads(strip_markdown_json(content))
                    return coerce_findings_payload(parsed)
                except (json.JSONDecodeError, RuntimeError) as exc:
                    logger.warning("JSON parse failed for model %s: %s | raw: %.200s", self.model, exc, content)
                    return []
        return []
