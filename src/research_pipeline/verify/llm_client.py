"""One LLM call on the configured backend (OpenAI, Gemini, Ollama, Codex CLI or Claude CLI)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import signal
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib import error, request

from ..llm.backends.claude_cli import claude_print_command, claude_workdir, cli_failure, turn_failure
from ..llm.failure_policy import (ContextOverflow, DeadlineExceeded, EmptyResponse, FailurePolicy, as_transient,
                                  run_with_policy)
from ..llm.rate_limit import UsageLimitReached, call_failure, is_daily_quota_exhausted
from ..llm.telemetry import response_event

_FENCE = re.compile(r"```(?:python|json)?\s*\n(.*?)```", re.DOTALL)
_OVERFLOW = re.compile(r"prompt is too long|context[_ ]length|maximum context|too many tokens", re.IGNORECASE)
_NO_TEXT = "não contém texto analisável"
_CALL_DEADLINE: ContextVar[float | None] = ContextVar("llm_call_deadline", default=None)


@contextmanager
def _hard_timeout(seconds: float | None):
    """Interrupt response reads too; socket inactivity timeouts alone are insufficient."""
    if seconds is None:
        yield
        return
    if seconds <= 0:
        raise TimeoutError("LLM call deadline exceeded")
    if not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        raise RuntimeError("A total LLM deadline requires the POSIX main thread")
    if signal.getitimer(signal.ITIMER_REAL)[0]:
        raise RuntimeError("Cannot replace an active process timer for an LLM deadline")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise TimeoutError("LLM call deadline exceeded")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _call_timeout(limit: float) -> float:
    deadline = _CALL_DEADLINE.get()
    if deadline is None:
        return limit
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("LLM call deadline exceeded")
    return min(limit, remaining)


def _pause(seconds: float) -> None:
    deadline = _CALL_DEADLINE.get()
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= seconds:
            time.sleep(max(0, remaining))
            raise TimeoutError("LLM call deadline exceeded during retry delay")
    time.sleep(seconds)


_MAX_UNTRUSTED_CHARS = 32_000


def _strip_fence(text: str) -> str:
    """Return the text inside the first ```python or ```json fence, or the text as-is."""
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
    """Text/JSON synthesis client for the configured API or CLI backend.

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
        isolated: bool = False,
        policy: FailurePolicy | None = None,
    ) -> None:
        self.isolated = isolated
        self.policy = policy or FailurePolicy()
        if backend not in {"openai", "ollama", "google", "codex", "claude_cli", "anthropic"}:
            raise ValueError(
                f"synth backend {backend!r} not supported yet; "
                "use 'openai', 'google', 'ollama', 'codex', 'claude_cli' or 'anthropic'."
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
            {"google": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(backend, "OPENAI_API_KEY")
        )
        if backend == "anthropic" and not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY não configurada para a síntese de harness.")
        if backend == "openai" and not self.api_key:
            raise ValueError("OPENAI_API_KEY não configurada para a síntese de harness.")
        if backend == "google" and not self.api_key:
            raise ValueError("GEMINI_API_KEY não configurada para a síntese de harness.")
        if backend == "ollama" and not self.api_key:
            self.api_key = "ollama"
        self.telemetry_events: list[dict] = []
        self.last_attempts = 1

    def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False,
                 timeout_seconds: float | None = None) -> SynthResult:
        """Optionally bound the entire call, including retries and their delays."""
        deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        token = _CALL_DEADLINE.set(deadline)
        try:
            with _hard_timeout(timeout_seconds):
                if self.policy.retries == 0:
                    return self._complete(system_prompt, user_prompt, json_mode=json_mode)
                outcome = run_with_policy(lambda prompt: self._attempt(system_prompt, prompt, json_mode),
                                          user_prompt, self.policy)
                result = outcome.value
                result.telemetry = {**result.telemetry, "operational_retries": outcome.retries,
                                    "context_reduced": outcome.context_reduced}
                return result
        finally:
            _CALL_DEADLINE.reset(token)

    def _attempt(self, system_prompt: str, user_prompt: str, json_mode: bool) -> SynthResult:
        """One try under a failure policy: provider symptoms become the policy's own exception types."""
        try:
            result = self._complete(system_prompt, user_prompt, json_mode=json_mode)
        except TimeoutError as exc:
            if "deadline exceeded" in str(exc):
                raise DeadlineExceeded(str(exc)) from exc
            raise
        except RuntimeError as exc:
            transient = as_transient(exc)
            if transient is not None:
                raise transient from exc
            if _NO_TEXT in str(exc):
                raise EmptyResponse(str(exc)) from exc
            if not isinstance(exc, UsageLimitReached) and _OVERFLOW.search(str(exc)):
                raise ContextOverflow(str(exc)) from exc
            raise
        if not result.raw_response.strip():
            raise EmptyResponse("resposta vazia")
        return result

    def _complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> SynthResult:
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
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        try:
            if self.backend == "codex":
                raw_response = self._run_codex(system_prompt, user_prompt)
            elif self.backend == "claude_cli":
                raw_response = self._run_claude_cli(system_prompt, user_prompt)
            elif self.backend == "anthropic":
                raw_response = self._run_anthropic(system_prompt, user_prompt)
            else:
                raw_response = self._post_json(payload)
        except Exception as exc:
            event = response_event(
                provider=self.backend, requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc, attempts=self.last_attempts,
            )
            self.telemetry_events.append(event)
            raise
        event = response_event(
            provider=self.backend, requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=raw_response, attempts=self.last_attempts,
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
                    timeout=_call_timeout(self.timeout_seconds),
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
                    raise call_failure(f"codex exec: turno falhou: {detail}", detail)
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
        command = claude_print_command(self.claude_command, model=self.model, system_prompt=system_prompt,
                                       user_prompt=user_prompt, isolated=self.isolated)

        # See backends/claude_cli.py: strip ANTHROPIC_API_KEY (leaked in via
        # main.py's load_dotenv) so `claude -p` uses the CLI's own subscription
        # login instead of that possibly-dead API key.
        env = {key: value for key, value in os.environ.items() if key != "ANTHROPIC_API_KEY"}

        try:
            with claude_workdir(self.isolated) as workdir:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=_call_timeout(self.timeout_seconds),
                    stdin=subprocess.DEVNULL,
                    env=env,
                    **workdir,
                )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Timeout ao chamar {self.claude_command} -p.") from exc
        except FileNotFoundError as exc:
            raise RuntimeError(f"Comando {self.claude_command!r} não encontrado no PATH.") from exc

        if completed.returncode != 0:
            raise cli_failure(self.claude_command, completed.returncode, completed.stdout, completed.stderr)
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{self.claude_command} -p não retornou JSON válido: {completed.stdout[:500]}"
            ) from exc
        if envelope.get("is_error"):
            raise turn_failure(self.claude_command, envelope.get("result"))

        return {
            "output_text": envelope.get("result", ""),
            "model": self.model,
            "reported_cost_usd": envelope.get("total_cost_usd"),
            "usage": envelope.get("usage") or {},
        }

    _ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

    def _run_anthropic(self, system_prompt: str, user_prompt: str, _retries: int = 3) -> dict:
        """Messages API, no extended thinking; returns the {"output_text", "usage", "model"} shape."""
        body = json.dumps({
            "model": self.model, "max_tokens": 16000, "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }).encode("utf-8")
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                   "Content-Type": "application/json"}
        for attempt in range(_retries):
            self.last_attempts = attempt + 1
            try:
                with request.urlopen(request.Request(self._ANTHROPIC_URL, data=body, headers=headers, method="POST"),
                                     timeout=_call_timeout(self.timeout_seconds)) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                if exc.code in (429, 500, 502, 503, 504, 529) and attempt < _retries - 1:
                    _pause(30 if exc.code == 429 else 2 ** (attempt + 2))
                    continue
                message = f"Falha ao chamar Anthropic Messages API: {exc.code} {details}"
                # Still rate-limited or overloaded after the retries: the next hypotheses would fail the same way.
                if exc.code in (429, 529):
                    raise UsageLimitReached(message) from exc
                raise call_failure(message, details) from exc
            except (error.URLError, TimeoutError) as exc:
                if attempt < _retries - 1:
                    _pause(2 ** attempt)
                    continue
                raise RuntimeError(f"Falha de rede ao chamar Anthropic Messages API: {exc}") from exc
        if data.get("stop_reason") == "max_tokens":
            raise RuntimeError("Anthropic Messages API: resposta cortada em max_tokens.")
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        return {"output_text": text, "model": data.get("model", self.model), "usage": data.get("usage", {})}

    def _post_json(self, payload: dict, _retries: int = 3) -> dict:
        if self.request_delay > 0:
            _pause(self.request_delay)
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(_retries):
            self.last_attempts = attempt + 1
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
                with request.urlopen(req, timeout=_call_timeout(self.timeout_seconds)) as response:
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and is_daily_quota_exhausted(details):
                    raise UsageLimitReached(f"Falha ao chamar OpenAI Responses API: {exc.code} {details}") from exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < _retries - 1:
                    sleep_time = 45 if exc.code == 429 else 2 ** (attempt + 2)
                    _pause(sleep_time)
                    continue
                raise call_failure(f"Falha ao chamar OpenAI Responses API: {exc.code} {details}", details) from exc
            except error.URLError as exc:
                if attempt < _retries - 1:
                    _pause(2 ** attempt)
                    continue
                raise RuntimeError(f"Falha de rede ao chamar OpenAI Responses API: {exc.reason}") from exc
            except TimeoutError as exc:
                if attempt < _retries - 1:
                    _pause(2 ** attempt)
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
