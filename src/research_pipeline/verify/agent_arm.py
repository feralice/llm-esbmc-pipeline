"""Experimental arm: an interactive agent (Claude Code + ESBMC plugin) builds the harness.

Nothing the agent reports is trusted. The pipeline re-runs ESBMC itself, replays the harness
under CPython and applies the same confirmation rule as the deterministic engine; a harness
whose target body differs from the original is reported apart.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from .astutil import expression_nodes, find_function
from research_pipeline.verification.esbmc_runner import run_esbmc_direct

from .hypothesis import BugHypothesis
from .outcome import CONFIRMED, classify_esbmc, final_verdict
from .render import Program
from .replay import ReplayVerdict, concrete_replay

AGENT_FAILED = "AGENT_FAILED"
# The agent changed the target's body: evidence about a rewrite, not about the original code.
AGENT_REWRITE_CONFIRMED = "AGENT_REWRITE_CONFIRMED"
PLUGIN_DIR = Path.home() / ".claude/plugins/cache/esbmc-marketplace/esbmc-plugin/1.1.0"

RunAgent = Callable[[str, Path, int], str]

_PROMPT = """Use the esbmc-verification skill. In this directory, original.py is real production code.

Goal: make ESBMC-Python run the function `{function}` so that this bug hypothesis is exercised.
- suspect expression: {expression}
- hypothesis: {trigger}

Write harness.py here. It must contain the code of `{function}` copied from original.py with its
body unchanged (you may add type annotations to its signature), plus whatever minimal stubs,
classes or helper definitions ESBMC needs, and a driver that calls `{function}` with nondet inputs
and runs at module level. Do not add assert statements and do not guard the suspect expression.
Run `{esbmc} harness.py --unwind {bound} --multi-property` (always this binary) and fix harness.py until ESBMC reaches a
verdict (VERIFICATION FAILED or SUCCESSFUL) instead of a conversion error. Then reply DONE.
"""


def claude_agent(claude_command: str = "claude", model: str | None = None,
                 esbmc: str = "/usr/local/bin/esbmc") -> RunAgent:
    def run(prompt: str, cwd: Path, timeout_seconds: int) -> str:
        command = [
            claude_command, "--print", "--output-format", "json", "--no-session-persistence",
            "--plugin-dir", str(PLUGIN_DIR),
            "--allowedTools", "Read", "Write", "Edit", f"Bash({esbmc}:*)", "Skill",
            "--permission-mode", "acceptEdits",
        ]
        if model:
            command += ["--model", model]
        command.append(prompt)
        # Same as the claude_cli backend: use the CLI's own login, not a leaked API key.
        env = {key: value for key, value in os.environ.items() if key != "ANTHROPIC_API_KEY"}
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False,
                                   timeout=timeout_seconds, stdin=subprocess.DEVNULL, env=env)
        try:
            return str(json.loads(completed.stdout).get("result", ""))
        except json.JSONDecodeError:
            return (completed.stdout or completed.stderr)[-2000:]
    return run


def _body(function: ast.FunctionDef) -> list[str]:
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return [ast.dump(stmt, include_attributes=False) for stmt in body]


def _target(tree: ast.Module, qualified: str) -> ast.FunctionDef | None:
    found = find_function(tree, qualified)
    if found is not None:
        return found
    name = qualified.split(".")[-1]
    matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    return matches[0] if len(matches) == 1 else None


def _without_esbmc_imports(source: str) -> str:
    """CPython has no ``esbmc`` module; the replay worker provides those names instead."""
    return re.sub(r"^(from esbmc import .*|import esbmc.*)$", "", source, flags=re.MULTILINE)


def run_agent_arm(
    h: BugHypothesis, *, work_dir: Path, run_agent: RunAgent, esbmc_command: list[str] | None,
    bound: int, timeout_seconds: int, agent_timeout: int = 900, source_path: Path | None = None,
) -> dict:
    started = time.monotonic()
    case_dir = Path(work_dir) / h.hypothesis_id
    case_dir.mkdir(parents=True, exist_ok=True)
    original = Path(source_path or h.file).read_text(encoding="utf-8", errors="replace")
    (case_dir / "original.py").write_text(original, encoding="utf-8")
    result = {"hypothesis": h.to_dict(), "verdict": AGENT_FAILED, "reason": "", "target_preserved": None,
              "replay": {}, "esbmc_status": "", "harness_path": str(case_dir / "harness.py")}

    def finish(verdict: str, reason: str = "") -> dict:
        result.update(verdict=verdict, reason=reason, seconds=round(time.monotonic() - started, 3))
        return result

    prompt = _PROMPT.format(function=h.function, expression=h.suspect_expression,
                            trigger=h.trigger_condition or "not given", bound=bound,
                            esbmc=(esbmc_command or ["esbmc"])[0])
    try:
        result["agent_output"] = run_agent(prompt, case_dir, agent_timeout)[-1000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return finish(AGENT_FAILED, f"agent did not finish: {type(exc).__name__}")
    harness_path = case_dir / "harness.py"
    if not harness_path.exists():
        return finish(AGENT_FAILED, "agent wrote no harness.py")
    harness = harness_path.read_text(encoding="utf-8", errors="replace")
    try:
        harness_tree, original_tree = ast.parse(harness), ast.parse(original)
    except SyntaxError as exc:
        return finish(AGENT_FAILED, f"harness does not parse: {exc.msg}")
    target = _target(harness_tree, h.function)
    if target is None:
        return finish(AGENT_FAILED, f"target {h.function} missing from the harness")
    nodes = expression_nodes(target, h.suspect_expression)
    if not nodes:
        return finish(AGENT_FAILED, "suspect expression missing from the harness target")
    original_target = _target(original_tree, h.function)
    result["target_preserved"] = original_target is not None and _body(original_target) == _body(target)

    esbmc = run_esbmc_direct(harness_path, esbmc_command=esbmc_command, bound=bound,
                             timeout_seconds=timeout_seconds, output_dir=case_dir,
                             bound_flags=["--unwind", str(bound)])
    reading = classify_esbmc(esbmc)
    result["esbmc_status"] = esbmc.status
    program = Program(_without_esbmc_imports(harness), 0,
                      tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes})), (),
                      (target.lineno, target.end_lineno))
    replay = (concrete_replay(program, target.name) if reading.kind in {"violation", "artifact", "safe"}
              else ReplayVerdict("unavailable", reason="ESBMC produced no verdict to validate"))
    result["replay"] = replay.to_dict()
    verdict = final_verdict(reading, replay)
    if verdict == CONFIRMED and not result["target_preserved"]:
        verdict = AGENT_REWRITE_CONFIRMED
    return finish(verdict, reading.message)
