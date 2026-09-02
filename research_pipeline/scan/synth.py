"""Step 3 of the scan mode: LLM harness synthesis.

Given a real function (CodeUnit) and a bug hypothesis (Finding), ask the LLM to
write a small self-contained ESBMC harness that models just the suspect
arithmetic. This is the piece the V1 pipeline never had: V1 runs ESBMC on the
original file with --function; here the LLM produces the model that ESBMC runs.

The prompt lives in research_pipeline/prompts/synth_prompt.txt.

This module DOES call a paid LLM API. It is only reached from --mode scan.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
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


def build_synth_user_prompt(unit: CodeUnit, finding: Finding) -> str:
    expression = str(finding.metadata.get("expression", "")) or "(not given)"
    return (
        f"Bug category: {finding.category}\n"
        f"Suspected unsafe expression: {expression}\n"
        f"Function name: {unit.name}\n"
        f"Parameters: {', '.join(unit.parameters) or '(none)'}\n"
        f"Type hints: {json.dumps(unit.type_hints)}\n\n"
        f"{format_precondition_block(unit.source)}\n\n"
        f"Real function source:\n```python\n{unit.source}\n```\n"
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
        if backend != "openai":
            raise ValueError(
                f"synth backend {backend!r} not supported yet; only 'openai'."
            )
        self.backend = backend
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY não configurada para a síntese de harness.")
        self.telemetry_events: list[dict] = []

    def synthesize(self, unit: CodeUnit, finding: Finding) -> SynthResult:
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": load_synth_prompt()}]},
                {"role": "user", "content": [{"type": "input_text", "text": build_synth_user_prompt(unit, finding)}]},
            ],
        }

        started = time.monotonic()
        try:
            raw_response = self._post_json(payload)
        except Exception as exc:
            event = response_event(
                provider="openai", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            )
            self.telemetry_events.append(event)
            raise
        event = response_event(
            provider="openai", requested_model=self.model,
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
    parts: list[str] = []
    for item in response_data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    if parts:
        return "\n".join(parts)
    raise RuntimeError("A resposta da OpenAI não contém texto analisável.")
