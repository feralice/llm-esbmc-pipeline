from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager

from ...models import CodeUnit, Finding
from ..findings import coerce_findings_payload, finding_from_dict, normalize_findings
from ..prompts import build_user_prompt, load_system_prompt
from ..rate_limit import call_failure
from ..schema import FINDINGS_JSON_SCHEMA, v2_findings_schema
from ..telemetry import response_event

# Tools this analysis task never needs: the function source is already in the
# prompt, so Read/Grep/Glob would only let the model wander the working
# directory, and Bash/Edit/Write/WebFetch have no legitimate role in a
# read-only classification call. Denying them explicitly is stronger than
# relying on --restricted alone, and keeps the guarantee auditable here
# instead of depending on what --restricted happens to cover this version.
_DENIED_TOOLS = "Read Write Edit Bash Glob Grep WebFetch WebSearch Task"


def claude_print_command(claude_command: str, *, model: str, system_prompt: str, user_prompt: str,
                         schema: dict | None = None, isolated: bool = False) -> list[str]:
    """The ``claude -p`` command line shared by detection and synthesis.

    ``isolated`` sends the pipeline prompt as the system prompt and drops tools, skills and MCP servers, so the
    call does not carry Claude Code's own context. Off by default: it changes what the model reads.
    """
    command = [claude_command, "--print", "--output-format", "json"]
    if schema is not None:
        command += ["--json-schema", json.dumps(schema)]
    command += ["--disallowed-tools", _DENIED_TOOLS, "--permission-prompts", "none", "--no-session-persistence"]
    if model:
        command += ["--model", model]
    if isolated:
        return command + ["--system-prompt", system_prompt, "--tools", "", "--disable-slash-commands",
                          "--strict-mcp-config", user_prompt]
    return command + [f"{system_prompt}\n\n{user_prompt}"]


@contextmanager
def claude_workdir(isolated: bool) -> Iterator[dict]:
    """Subprocess kwargs: an isolated call runs in an empty directory, so no project CLAUDE.md is read."""
    if not isolated:
        yield {}
        return
    with tempfile.TemporaryDirectory(prefix="claude_isolated_") as directory:
        yield {"cwd": directory}


def cli_failure_detail(stdout: str, stderr: str) -> str:
    """Why ``claude -p`` exited non-zero: with ``--output-format json`` the reason (usage limit, unknown
    model) is the envelope's ``result`` on stdout, and stderr is often empty."""
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        envelope = None
    if isinstance(envelope, dict) and envelope.get("result"):
        status = envelope.get("api_error_status")
        return (f"[{status}] " if status else "") + str(envelope["result"])[:500]
    return (stderr.strip() or stdout.strip())[:500]


def cli_failure(command: str, returncode: int, stdout: str, stderr: str) -> RuntimeError:
    """The error for a ``claude -p`` that exited non-zero; UsageLimitReached when the plan's limit stopped it."""
    detail = cli_failure_detail(stdout, stderr)
    return call_failure(f"{command} -p saiu com código {returncode}: {detail}", detail)


def turn_failure(command: str, result: object) -> RuntimeError:
    return call_failure(f"{command} -p: turno falhou: {result}", str(result))


class ClaudeCliAnalyzer:
    """LLM analyzer backed by the local `claude -p` CLI (Claude Code).

    Bills against whatever Claude subscription/API access the account already
    has instead of requiring a separate OPENAI_API_KEY/GEMINI_API_KEY -- the
    same "no metered API key needed" niche CodexAnalyzer fills for ChatGPT/Codex
    plans. --json-schema gives strict structured output the same way OpenAI's
    Responses API does, so no markdown-fence stripping is needed here.
    """

    def __init__(
        self,
        model: str = "",
        timeout_seconds: int = 300,
        claude_command: str = "claude",
        include_smells: bool = True,
        v2_detection: bool = False,
        v2_variants: tuple[str, ...] = (),
        isolated: bool = False,
    ) -> None:
        self.isolated = isolated
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.claude_command = claude_command
        self.include_smells = include_smells
        self.v2_detection = v2_detection
        self.v2_variants = v2_variants
        self.telemetry_events: list[dict] = []

    def analyze(self, unit: CodeUnit) -> list[Finding]:
        started = time.monotonic()
        try:
            response = self._run_cli(
                load_system_prompt(include_smells=self.include_smells, v2_detection=self.v2_detection, v2_variants=self.v2_variants),
                build_user_prompt(unit, include_smells=self.include_smells, v2_variants=self.v2_variants),
            )
            findings = [finding_from_dict(item) for item in coerce_findings_payload(response["payload"])]
            result = normalize_findings(unit, findings, v2_detection=self.v2_detection)
        except Exception as exc:
            self.telemetry_events.append(response_event(
                provider="claude_cli",
                requested_model=self.model,
                duration_seconds=time.monotonic() - started,
                error=exc,
            ))
            raise
        self.telemetry_events.append(response_event(
            provider="claude_cli",
            requested_model=self.model,
            duration_seconds=time.monotonic() - started,
            response=response,
        ))
        return result


    def _run_cli(self, system_prompt: str, user_prompt: str, schema: dict | None = None) -> dict:
        schema = schema or (v2_findings_schema(self.v2_variants) if self.v2_detection else FINDINGS_JSON_SCHEMA)["schema"]
        command = claude_print_command(self.claude_command, model=self.model, system_prompt=system_prompt,
                                       user_prompt=user_prompt, schema=schema, isolated=self.isolated)

        # main.py's load_dotenv() puts .env's ANTHROPIC_API_KEY in this process's
        # environment for the openai/anthropic backends; inherited as-is, it makes
        # `claude -p` bill/authenticate against that (possibly dead) API key instead
        # of the CLI's own subscription login, defeating this backend's purpose.
        env = {key: value for key, value in os.environ.items() if key != "ANTHROPIC_API_KEY"}

        try:
            with claude_workdir(self.isolated) as workdir:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
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
        if "structured_output" not in envelope:
            raise RuntimeError(
                f"{self.claude_command} -p não retornou structured_output "
                "(verifique se --json-schema é suportado nesta versão)."
            )

        return {
            "payload": envelope["structured_output"],
            "model": self.model,
            "reported_cost_usd": envelope.get("total_cost_usd"),
            "usage": envelope.get("usage") or {},
        }
