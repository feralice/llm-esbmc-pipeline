"""One LLM call on the configured backend (OpenAI, Gemini, Ollama, Codex CLI or Claude CLI)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request

from ..llm.rate_limit import is_daily_quota_exhausted
from ..llm.telemetry import response_event

_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


_MAX_UNTRUSTED_CHARS = 32_000


def _strip_fence(text: str) -> str:
    """Return the code inside the first ```python fence, or the text as-is."""
    match = _FENCE.search(text)
    if match:
        return match.group(1).strip() + "\n"
    return text.strip() + "\n"


def _bound_untrusted(value: str, max_chars: int = _MAX_UNTRUSTED_CHARS) -> str:
    """Bound untrusted prompt content and make omitted text explicit."""
    if len(value) <= max_chars:
        return value
    marker = "\n[UNTRUSTED_CONTEXT_TRUNCATED]\n"
    available = max_chars - len(marker)
    if available <= 0:
        return marker[:max_chars]
    head = available * 3 // 4
    return value[:head] + marker + value[-(available - head):]


@dataclass
class SynthResult:
    """Outcome of one harness-synthesis call."""

    harness: str                       # the extracted harness source (fence stripped)
    raw_response: str                  # full model text, for debugging
    model: str
    telemetry: dict = field(default_factory=dict)


class LLMClient:
    """OpenAI-backed harness synthesizer (Responses API, plain-text output).

    Kept separate from research_pipeline.llm.backends.* because those analyzers
    are hard-wired to the findings JSON schema; synthesis needs free-form text.
    """

    def __init__(
        self,
        *,
        backend: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 120,
        codex_command: str = "codex",
        claude_command: str = "claude",
        request_delay: float = 0.0,
    ) -> None:
        if backend not in {"openai", "ollama", "google", "codex", "claude_cli"}:
            raise ValueError(
                f"synth backend {backend!r} not supported yet; "
                "use 'openai', 'google', 'ollama', 'codex' or 'claude_cli'."
            )
        self.backend = backend
        self.model = model
        self.request_delay = request_delay
        self.base_url = (
            base_url.rstrip("/") + "/chat/completions"
            if backend in {"ollama", "google"} and not base_url.rstrip("/").endswith("/chat/completions")
            else base_url
        )
        self.timeout_seconds = timeout_seconds
        self.codex_command = codex_command
        self.claude_command = claude_command
        self.api_key = api_key or os.environ.get(
            "GEMINI_API_KEY" if backend == "google" else "OPENAI_API_KEY"
        )
        if backend == "openai" and not self.api_key:
            raise ValueError("OPENAI_API_KEY não configurada para a síntese de harness.")
        if backend == "google" and not self.api_key:
            raise ValueError("GEMINI_API_KEY não configurada para a síntese de harness.")
        if backend == "ollama" and not self.api_key:
            self.api_key = "ollama"
        self.telemetry_events: list[dict] = []

    def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> SynthResult:
        """One call to the configured backend; the fence-stripped text lands in ``harness``."""
        payload: dict[str, Any] = {}
        if self.backend == "openai":
            payload = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                ],
            }
            if json_mode:
                payload["text"] = {"format": {"type": "json_object"}}
        elif self.backend in {"ollama", "google"}:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "stream": False,
            }

        started = time.monotonic()
        try:
            if self.backend == "codex":
                raw_response = self._run_codex(system_prompt, user_prompt)
            elif self.backend == "claude_cli":
                raw_response = self._run_claude_cli(system_prompt, user_prompt)
            else:
                raw_response = self._post_json(payload)
        except Exception as exc:
            event = response_event(
                provider=self.backend, requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            )
            self.telemetry_events.append(event)
            raise
        event = response_event(
            provider=self.backend, requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=raw_response,
        )
        self.telemetry_events.append(event)

        text = _extract_output_text(raw_response)
        return SynthResult(
            harness=_strip_fence(text),
            raw_response=text,
            model=self.model,
            telemetry=event,
        )

    def _run_codex(self, system_prompt: str, user_prompt: str) -> dict:
        """Synthesize via the local `codex exec` CLI instead of a metered API call.

        Bills against whatever ChatGPT/ Codex plan the account already has,
        not per-token. Returns the same {"output_text", "usage", "model"}
        shape _post_json's callers expect, so response_event() and
        _extract_output_text() need no special-casing for this backend.
        """
        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".txt", delete=False, encoding="utf-8"
        ) as handle:
            out_path = Path(handle.name)
        try:
            command = [
                self.codex_command, "exec",
                "--sandbox", "read-only",
                "--json",
                "-o", str(out_path),
            ]
            if self.model:
                command += ["-m", self.model]
            command.append(f"{system_prompt}\n\n{user_prompt}")

            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    stdin=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError(f"Timeout ao chamar {self.codex_command} exec.") from exc
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"Comando {self.codex_command!r} não encontrado no PATH."
                ) from exc

            usage: dict[str, int] = {}
            returned_model = None
            for line in completed.stdout.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "turn.completed":
                    usage = event.get("usage") or {}
                elif event.get("type") == "turn.failed":
                    detail = json.dumps(event.get("error") or event, ensure_ascii=False)
                    raise RuntimeError(f"codex exec: turno falhou: {detail}")
                if isinstance(event.get("model"), str):
                    returned_model = event["model"]

            if completed.returncode != 0 or not out_path.exists():
                raise RuntimeError(
                    f"codex exec saiu com código {completed.returncode}: "
                    f"{completed.stderr.strip()[:500]}"
                )
            output_text = out_path.read_text(encoding="utf-8")
        finally:
            out_path.unlink(missing_ok=True)

        return {
            "output_text": output_text,
            "model": returned_model or self.model,
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            },
        }

    def _run_claude_cli(self, system_prompt: str, user_prompt: str) -> dict:
        """Synthesize via the local `claude -p` CLI instead of a metered API call.

        Unlike `_run_codex`, no --json-schema here: the harness is free-form
        Python wrapped in a ```python fence, not a JSON object, so the plain
        text `result` field is what _extract_output_text()/_strip_fence()
        already expect from every other backend.
        """
        command = [
            self.claude_command, "--print",
            "--output-format", "json",
            "--disallowed-tools", "Read Write Edit Bash Glob Grep WebFetch WebSearch Task",
            "--permission-prompts", "none",
            "--no-session-persistence",
        ]
        if self.model:
            command += ["--model", self.model]
        command.append(f"{system_prompt}\n\n{user_prompt}")

        # See backends/claude_cli.py: strip ANTHROPIC_API_KEY (leaked in via
        # main.py's load_dotenv) so `claude -p` uses the CLI's own subscription
        # login instead of that possibly-dead API key.
        env = {key: value for key, value in os.environ.items() if key != "ANTHROPIC_API_KEY"}

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                stdin=subprocess.DEVNULL,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Timeout ao chamar {self.claude_command} -p.") from exc
        except FileNotFoundError as exc:
            raise RuntimeError(f"Comando {self.claude_command!r} não encontrado no PATH.") from exc

        if completed.returncode != 0:
            raise RuntimeError(
                f"{self.claude_command} -p saiu com código {completed.returncode}: "
                f"{completed.stderr.strip()[:500]}"
            )
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{self.claude_command} -p não retornou JSON válido: {completed.stdout[:500]}"
            ) from exc
        if envelope.get("is_error"):
            raise RuntimeError(f"{self.claude_command} -p: turno falhou: {envelope.get('result')}")

        usage = envelope.get("usage") or {}
        return {
            "output_text": envelope.get("result", ""),
            "model": self.model,
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            },
        }

    def _post_json(self, payload: dict, _retries: int = 3) -> dict:
        if self.request_delay > 0:
            time.sleep(self.request_delay)
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(_retries):
            req = request.Request(
                self.base_url,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.api_key or 'ollama'}",
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
                    sleep_time = 45 if exc.code == 429 else 2 ** (attempt + 2)
                    time.sleep(sleep_time)
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


def _extract_output_text(response_data: dict) -> str:
    if isinstance(response_data.get("output_text"), str):
        return response_data["output_text"]
    choices = response_data.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content")
        if isinstance(content, str) and content.strip():
            return content
    parts: list[str] = []
    for item in response_data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    if parts:
        return "\n".join(parts)
    raise RuntimeError("A resposta da OpenAI não contém texto analisável.")
