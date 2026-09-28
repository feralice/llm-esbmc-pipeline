from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

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


class CodexAnalyzer:
    """LLM analyzer backed by the local ``codex exec`` CLI.

    The CLI returns plain text in the output file. The deterministic findings
    parser and AST grounding step remain the same as the API backends.
    """

    def __init__(
        self,
        model: str = "",
        timeout_seconds: int = 300,
        codex_command: str = "codex",
        include_smells: bool = True,
        v2_categories: bool = False,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.codex_command = codex_command
        self.include_smells = include_smells
        self.v2_categories = v2_categories
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        started = time.monotonic()
        try:
            response = self._run_cli(
                load_system_prompt(include_smells=self.include_smells, v2_categories=self.v2_categories),
                build_user_prompt(unit, include_smells=self.include_smells, v2_categories=self.v2_categories),
            )
            payload = json.loads(strip_markdown_json(response["output_text"]))
            findings = [finding_from_dict(item) for item in coerce_findings_payload(payload)]
            result = normalize_findings(unit, findings)
        except Exception as exc:
            self.telemetry_events.append(response_event(
                provider="codex",
                requested_model=self.model,
                duration_seconds=time.monotonic() - started,
                error=exc,
            ))
            raise
        self.telemetry_events.append(response_event(
            provider="codex",
            requested_model=self.model,
            duration_seconds=time.monotonic() - started,
            response=response,
        ))
        return result

    def analyze_stage(self, unit, *, stage, candidates=None):
        started = time.monotonic()
        try:
            response = self._run_cli(
                build_stage_system_prompt(stage),
                build_stage_user_prompt(unit, stage=stage, candidates=candidates),
            )
            payload = json.loads(strip_markdown_json(response["output_text"]))
            result = parse_stage_payload(payload, stage=stage, candidates=candidates)
        except Exception as exc:
            event = response_event(
                provider="codex", requested_model=self.model,
                duration_seconds=time.monotonic() - started, error=exc,
            )
            event["analysis_stage"] = stage
            self.telemetry_events.append(event)
            raise
        event = response_event(
            provider="codex", requested_model=self.model,
            duration_seconds=time.monotonic() - started, response=response,
        )
        event["analysis_stage"] = stage
        self.telemetry_events.append(event)
        return result

    def _run_cli(self, system_prompt: str, user_prompt: str) -> dict:
        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".txt", delete=False, encoding="utf-8"
        ) as handle:
            output_path = Path(handle.name)
        try:
            command = [
                self.codex_command,
                "exec",
                "--sandbox",
                "read-only",
                "--json",
                "-o",
                str(output_path),
            ]
            if self.model:
                command.extend(["-m", self.model])
            command.append(
                f"{system_prompt}\n\n{user_prompt}\n\n"
                "Return only the JSON object required by the schema."
            )
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
                raise RuntimeError(f"Comando {self.codex_command!r} não encontrado no PATH.") from exc

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

            if completed.returncode != 0 or not output_path.exists():
                raise RuntimeError(
                    f"codex exec saiu com código {completed.returncode}: "
                    f"{completed.stderr.strip()[:500]}"
                )
            return {
                "output_text": output_path.read_text(encoding="utf-8"),
                "model": returned_model or self.model,
                "usage": {
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                },
            }
        finally:
            output_path.unlink(missing_ok=True)
