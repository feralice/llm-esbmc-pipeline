"""V2 step 3: LLM harness synthesis.

Given a real function (CodeUnit) and a bug hypothesis (Finding), ask the LLM to
write a small self-contained ESBMC harness that models just the suspect
arithmetic. This is the piece the V1 pipeline never had: V1 runs ESBMC on the
original file with --function; here the LLM produces the model that ESBMC runs.

The prompt lives in research_pipeline/prompts/synth_prompt.txt.

This module DOES call a paid LLM API. It is only reached from --mode v2.
"""

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

from ..llm.telemetry import response_event
from ..models import CodeUnit, Finding
from .guards import format_precondition_block

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

STYLE_SCALAR = "scalar"
STYLE_DRIVER = "driver"
STYLE_LOOP = "loop"

_PROMPT_FILES = {
    STYLE_SCALAR: "synth_prompt.txt",
    STYLE_DRIVER: "driver_prompt.txt",
    STYLE_LOOP: "synth_prompt_loop.txt",
}


def load_synth_prompt(style: str = STYLE_SCALAR) -> str:
    path = _PROMPT_DIR / _PROMPT_FILES.get(style, _PROMPT_FILES[STYLE_SCALAR])
    return path.read_text(encoding="utf-8").strip()


def _strip_fence(text: str) -> str:
    """Return the code inside the first ```python fence, or the text as-is."""
    match = _FENCE.search(text)
    if match:
        return match.group(1).strip() + "\n"
    return text.strip() + "\n"


_NO_GUARDS_BLOCK = (
    "Preconditions the real function enforces: NOT PROVIDED for this run.\n"
    "Add only one loose magnitude bound per variable so the search terminates "
    "(e.g. __ESBMC_assume(abs(x) <= 1000)). Add NO other precondition."
)


def build_synth_user_prompt(
    unit: CodeUnit,
    finding: Finding,
    *,
    use_guards: bool = True,
    repair_feedback: str = "",
    previous_harness: str = "",
    style: str = STYLE_SCALAR,
) -> str:
    expression = str(finding.metadata.get("expression", "")) or "(not given)"
    if use_guards:
        precondition = format_precondition_block(unit.source)
    else:
        precondition = _NO_GUARDS_BLOCK
    fixed_behaviour = str(finding.metadata.get("fixed_behaviour", "")).strip()
    fixed_block = (
        f"\nIntended (fixed) behaviour:\n{fixed_behaviour}\n"
        if style in {STYLE_DRIVER, STYLE_LOOP} and fixed_behaviour
        else ""
    )
    repair_block = ""
    if repair_feedback:
        repair_block = (
            "\n\nREPAIR REQUIRED\n"
            "The previous harness was rejected by deterministic validation. "
            "Correct only the reported problems; preserve the original suspect "
            "expression's semantics and do not fabricate a fix.\n"
            f"Validator feedback:\n{repair_feedback}\n"
            f"Previous rejected harness:\n```python\n{previous_harness}\n```\n"
        )
    return (
        f"Bug category: {finding.category}\n"
        f"Suspected unsafe expression: {expression}\n"
        f"Function name: {unit.name}\n"
        f"Parameters: {', '.join(unit.parameters) or '(none)'}\n"
        f"Type hints: {json.dumps(unit.type_hints)}\n\n"
        f"{precondition}\n"
        f"{fixed_block}\n"
        f"Real function source:\n```python\n{unit.source}\n```\n"
        f"{repair_block}"
    )


@dataclass
class SynthResult:
    """Outcome of one harness-synthesis call."""

    harness: str                       # the extracted harness source (fence stripped)
    raw_response: str                  # full model text, for debugging
    model: str
    telemetry: dict = field(default_factory=dict)


class HarnessSynthesizer:
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
    ) -> None:
        if backend not in {"openai", "ollama", "codex"}:
            raise ValueError(
                f"synth backend {backend!r} not supported yet; use 'openai', 'ollama' or 'codex'."
            )
        self.backend = backend
        self.model = model
        self.base_url = (
            base_url.rstrip("/") + "/chat/completions"
            if backend == "ollama" and not base_url.rstrip("/").endswith("/chat/completions")
            else base_url
        )
        self.timeout_seconds = timeout_seconds
        self.codex_command = codex_command
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if backend == "openai" and not self.api_key:
            raise ValueError("OPENAI_API_KEY não configurada para a síntese de harness.")
        if backend == "ollama" and not self.api_key:
            self.api_key = "ollama"
        self.telemetry_events: list[dict] = []

    def synthesize(
        self,
        unit: CodeUnit,
        finding: Finding,
        *,
        use_guards: bool = True,
        repair_feedback: str = "",
        previous_harness: str = "",
        style: str = STYLE_SCALAR,
    ) -> SynthResult:
        system_prompt = load_synth_prompt(style)
        user_prompt = build_synth_user_prompt(
            unit,
            finding,
            use_guards=use_guards,
            repair_feedback=repair_feedback,
            previous_harness=previous_harness,
            style=style,
        )
        payload: dict[str, Any] = {}
        if self.backend == "openai":
            payload = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                ],
            }
        elif self.backend == "ollama":
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
            raw_response = (
                self._run_codex(system_prompt, user_prompt)
                if self.backend == "codex"
                else self._post_json(payload)
            )
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

    def _post_json(self, payload: dict, _retries: int = 3) -> dict:
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
