from __future__ import annotations

import json
import os
import subprocess
import time

from ...models import CodeUnit, Finding
from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings, strip_markdown_json
from ..prompts import build_user_prompt, load_system_prompt
from ..telemetry import response_event


class GeminiCliAnalyzer:
    """LLM analyzer backed by the authenticated local ``gemini`` CLI."""

    def __init__(self, model: str = "", timeout_seconds: int = 300,
                 gemini_command: str = "gemini", include_smells: bool = True) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.gemini_command = gemini_command
        self.include_smells = include_smells
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        started = time.monotonic()
        try:
            response = self._run_cli(
                load_system_prompt(include_smells=self.include_smells),
                build_user_prompt(unit, include_smells=self.include_smells),
            )
            payload = response["response"]
            if isinstance(payload, str):
                payload = json.loads(strip_markdown_json(payload))
            findings = [finding_from_dict(item) for item in coerce_findings_payload(payload)]
            result = normalize_findings(unit, findings)
        except Exception as exc:
            self.telemetry_events.append(response_event(
                provider="gemini_cli", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            ))
            raise
        self.telemetry_events.append(response_event(
            provider="gemini_cli", requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=response,
        ))
        return result

    def _run_cli(self, system_prompt: str, user_prompt: str) -> dict:
        prompt = f"{system_prompt}\n\n{user_prompt}\n\nReturn only the JSON object required by the schema."
        command = [
            self.gemini_command, "--prompt", prompt, "--output-format", "json",
            "--approval-mode", "plan", "--skip-trust",
        ]
        if self.model:
            command += ["--model", self.model]
        env = {key: value for key, value in os.environ.items()
               if key not in {"GEMINI_API_KEY", "GOOGLE_API_KEY"}}
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True,
                timeout=self.timeout_seconds, stdin=subprocess.DEVNULL, env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Timeout ao chamar {self.gemini_command}.") from exc
        except FileNotFoundError as exc:
            raise RuntimeError(f"Comando {self.gemini_command!r} não encontrado no PATH.") from exc
        if completed.returncode != 0:
            raise RuntimeError(
                f"{self.gemini_command} saiu com código {completed.returncode}: "
                f"{completed.stderr.strip()[:500]}"
            )
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{self.gemini_command} não retornou JSON válido: {completed.stdout[:500]}"
            ) from exc
        if envelope.get("error"):
            raise RuntimeError(f"{self.gemini_command}: {envelope['error']}")
        if "response" not in envelope:
            raise RuntimeError(f"{self.gemini_command} não retornou o campo response.")
        return {"response": envelope["response"], "model": self.model,
                "usage": envelope.get("stats") or {}}
