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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request

from ..llm.telemetry import response_event
from ..models import CodeUnit, Finding
from .guards import format_precondition_block

_SYNTH_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "synth_prompt.txt"

_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def load_synth_prompt() -> str:
    return _SYNTH_PROMPT_PATH.read_text(encoding="utf-8").strip()


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
) -> str:
    expression = str(finding.metadata.get("expression", "")) or "(not given)"
    if use_guards:
        precondition = format_precondition_block(unit.source)
    else:
        precondition = _NO_GUARDS_BLOCK
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
        f"{precondition}\n\n"
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
    ) -> None:
        if backend not in {"openai", "ollama"}:
            raise ValueError(
                f"synth backend {backend!r} not supported yet; use 'openai' or 'ollama'."
            )
        self.backend = backend
        self.model = model
        self.base_url = (
            base_url.rstrip("/") + "/chat/completions"
            if backend == "ollama" and not base_url.rstrip("/").endswith("/chat/completions")
            else base_url
        )
        self.timeout_seconds = timeout_seconds
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
    ) -> SynthResult:
        user_prompt = build_synth_user_prompt(
            unit,
            finding,
            use_guards=use_guards,
            repair_feedback=repair_feedback,
            previous_harness=previous_harness,
        )
        payload: dict[str, Any]
        if self.backend == "openai":
            payload = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": load_synth_prompt()}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                ],
            }
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": load_synth_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "stream": False,
            }

        started = time.monotonic()
        try:
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
