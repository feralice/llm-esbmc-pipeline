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
import textwrap
import time
from pathlib import Path
from typing import Callable

from .astutil import expression_nodes, find_function
from .context import context_module

from .hypothesis import BugHypothesis
from .esbmc_run import VERDICT_KINDS, check, esbmc_output
from .outcome import CONFIRMED, final_verdict
from .render import Program
from .replay import ReplayVerdict, concrete_replay, counterexample_seeds

AGENT_FAILED = "AGENT_FAILED"
# The agent simplified the target's body for ESBMC, and ESBMC's counterexample values, replayed on the
# ORIGINAL body under CPython, raise the hypothesis's exception at the suspect expression.
CONFIRMED_SIMPLIFIED = "CONFIRMED_SIMPLIFIED"
PLUGIN_DIR = Path.home() / ".claude/plugins/cache/esbmc-marketplace/esbmc-plugin/1.1.0"

RunAgent = Callable[[str, Path, int], str]

_SKILL = "Use the esbmc-verification skill. "
_NOTES = "Read ESBMC_PYTHON_NOTES.md first: it lists what ESBMC-Python accepts and how to work around the rest.\n"
_SIMPLIFY = """If ESBMC rejects a construct inside the function body itself, you may simplify that construct
only (keep the function's name, signature, the suspect expression and the branches leading to it).
The original body is replayed later with ESBMC's counterexample values, so a simplification that
changes behaviour simply fails to confirm.
"""
_PROMPT = """{skill}In this directory, original.py is real production code.
{notes}
Goal: make ESBMC-Python run the function `{function}` so that this bug hypothesis is exercised.
- suspect expression: {expression}
- hypothesis: {trigger}

Write harness.py here. It must contain the code of `{function}` copied from original.py with its
body unchanged (you may add type annotations to its signature), plus whatever minimal stubs,
classes or helper definitions ESBMC needs, and a driver that calls `{function}` with nondet inputs
and runs at module level. Keep every stub inside harness.py: do not create or import other local
modules (the CPython replay runs harness.py alone). Do not add assert statements and do not guard
the suspect expression.
{simplify}Run `{esbmc} harness.py --unwind {bound} --multi-property` (always this binary) and fix harness.py until ESBMC reaches a
verdict (VERIFICATION FAILED or SUCCESSFUL) instead of a conversion error. Then reply DONE.
"""


def claude_agent(claude_command: str = "claude", model: str | None = None,
                 esbmc: str = "/usr/local/bin/esbmc", *, plugin: bool = True, isolated: bool = True) -> RunAgent:
    """``isolated`` loads no user settings (globally enabled plugins, hooks), so the ESBMC plugin is
    present exactly when ``plugin`` asks for it: the variants of an experiment differ in one thing."""
    def run(prompt: str, cwd: Path, timeout_seconds: int) -> str:
        command = [claude_command, "--print", "--output-format", "json", "--no-session-persistence",
                   *(["--setting-sources", "project"] if isolated else []),
                   *(["--plugin-dir", str(PLUGIN_DIR)] if plugin else []),
                   # The plugin's commands call plain `esbmc` (and `which`); PATH below points it at this binary.
                   "--allowedTools", "Read", "Write", "Edit", f"Bash({esbmc}:*)", "Bash(esbmc:*)", "Bash(which:*)",
                   *(["Skill", "Agent", "Task"] if plugin else []),
                   "--permission-mode", "acceptEdits"]
        if model:
            command += ["--model", model]
        command.append(prompt)
        # Same as the claude_cli backend: use the CLI's own login, not a leaked API key.
        env = {key: value for key, value in os.environ.items() if key != "ANTHROPIC_API_KEY"}
        env["PATH"] = os.pathsep.join([str(Path(esbmc).parent), env.get("PATH", "")])
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False,
                                   timeout=timeout_seconds, stdin=subprocess.DEVNULL, env=env)
        try:
            return str(json.loads(completed.stdout).get("result", ""))
        except json.JSONDecodeError:
            return (completed.stdout or completed.stderr)[-2000:]
    return run


NOTES_PATH = Path(__file__).with_name("esbmc_python_notes.md")
_SOURCE_LIMIT = 40_000
_API_SYSTEM = """You write verification harnesses for ESBMC-Python. You cannot run tools: reply with the
complete harness.py in one ```python code block and nothing else. The pipeline runs ESBMC on it and
sends you its output; fix the harness until ESBMC reaches VERIFICATION FAILED or SUCCESSFUL.

{notes}"""


def api_agent(llm, *, rounds: int = 8, esbmc: str = "/usr/local/bin/esbmc", bound: int = 5,
              esbmc_timeout: int = 120) -> RunAgent:
    """The agent's loop for any chat API (OpenAI, Gemini, Ollama, Claude CLI): the model proposes
    harness.py, the pipeline runs ESBMC and returns its errors, for at most ``rounds`` turns. Its
    harness then goes through the same checks as the Claude Code agent's."""
    def run(prompt: str, cwd: Path, timeout_seconds: int) -> str:
        deadline = time.monotonic() + timeout_seconds
        notes = cwd / "ESBMC_PYTHON_NOTES.md"
        system = _API_SYSTEM.format(notes=(notes if notes.exists() else NOTES_PATH).read_text(encoding="utf-8"))
        task = f"{prompt}\noriginal.py:\n```python\n{_source_for(cwd, prompt)}\n```"
        feedback = ""
        for _ in range(rounds):
            if time.monotonic() > deadline:
                return "out of time"
            try:
                reply = llm.complete(system, task + feedback)
            except Exception as exc:  # noqa: BLE001 - an API failure ends this case, not the run
                return f"API error: {type(exc).__name__}: {str(exc)[:200]}"
            harness = reply.harness.strip()
            if not harness:
                feedback = "\n\nYour reply had no python code block. Reply with the complete harness.py."
                continue
            (cwd / "harness.py").write_text(harness + "\n", encoding="utf-8")
            try:
                done = subprocess.run([esbmc, "harness.py", "--unwind", str(bound), "--multi-property"], cwd=cwd,
                                      capture_output=True, text=True, timeout=esbmc_timeout, check=False)
                output = done.stdout + done.stderr
            except subprocess.TimeoutExpired:
                output = "ESBMC timed out: simplify the stubs or bound the inputs."
            if "VERIFICATION FAILED" in output or "VERIFICATION SUCCESSFUL" in output:
                return "DONE"
            errors = [line for line in output.splitlines() if "ERROR" in line or "error" in line or "WARNING" in line]
            feedback = (f"\n\nYour previous harness.py:\n```python\n{harness}\n```\nESBMC output:\n"
                        + "\n".join((errors or output.splitlines())[-30:]))
        return "no verdict"
    return run


def _source_for(cwd: Path, prompt: str) -> str:
    """original.py, or for a large file the target with the definitions it reaches (verbatim)."""
    source = (cwd / "original.py").read_text(encoding="utf-8", errors="replace")
    if len(source) <= _SOURCE_LIMIT:
        return source
    match = re.search(r"run the function `([^`]+)`", prompt)
    sliced = context_module(source, match.group(1)) if match else ""
    return sliced or source[:_SOURCE_LIMIT]


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
    skill: bool = True, notes: Path | None = None, plugin_command: str = "", allow_simplify: bool = False,
) -> dict:
    """``skill`` names the plugin's skill in the prompt; ``notes`` is copied next to original.py;
    ``plugin_command`` (verify or audit) runs on the harness afterwards and its report is kept."""
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

    if notes is not None:
        (case_dir / "ESBMC_PYTHON_NOTES.md").write_text(Path(notes).read_text(encoding="utf-8"), encoding="utf-8")
    prompt = _PROMPT.format(skill=_SKILL if skill else "", notes=_NOTES if notes is not None else "",
                            simplify=_SIMPLIFY if allow_simplify else "",
                            function=h.function, expression=h.suspect_expression,
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
    verdict, reason = evaluate_harness(h, harness, original, case_dir, result, esbmc_command=esbmc_command,
                                       bound=bound, timeout_seconds=timeout_seconds)
    if plugin_command and result.get("target_preserved"):
        result["plugin_report"] = plugin_report(run_agent, plugin_command, case_dir, agent_timeout)
    return finish(verdict, reason)


def plugin_report(run_agent: RunAgent, command: str, case_dir: Path, timeout_seconds: int) -> str:
    """Run one of the plugin's commands (verify, audit) on the finished harness and keep its report.
    The report explains the case; it never sets the verdict, which the pipeline computes itself."""
    try:
        text = run_agent(f"/esbmc-plugin:{command} harness.py", case_dir, timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        text = f"plugin command did not finish: {type(exc).__name__}"
    path = case_dir / f"plugin_{command}.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def evaluate_harness(h: BugHypothesis, harness: str, original: str, case_dir: Path, result: dict, *,
                     esbmc_command: list[str] | None, bound: int, timeout_seconds: int,
                     output_dir: Path | None = None) -> tuple[str, str]:
    """Re-run ESBMC on an agent's harness and replay it; fills ``result`` and returns (verdict, reason).
    Also re-checks harnesses saved by earlier runs without calling the agent again; ``output_dir`` keeps
    that check's ESBMC logs apart from the original run's."""
    harness_path = case_dir / "harness.py"
    try:
        harness_tree, original_tree = ast.parse(harness), ast.parse(original)
    except SyntaxError as exc:
        return AGENT_FAILED, f"harness does not parse: {exc.msg}"
    target = _target(harness_tree, h.function)
    if target is None:
        return AGENT_FAILED, f"target {h.function} missing from the harness"
    nodes = expression_nodes(target, h.suspect_expression)
    if not nodes:
        return AGENT_FAILED, "suspect expression missing from the harness target"
    original_target = _target(original_tree, h.function)
    result["target_preserved"] = original_target is not None and _body(original_target) == _body(target)

    esbmc, reading, how = check(harness_path, esbmc_command=esbmc_command, bound=bound,
                                timeout_seconds=timeout_seconds, work_dir=output_dir or case_dir)
    result.update(esbmc_status=esbmc.status, **how)
    seeds = counterexample_seeds(esbmc_output(esbmc), None)
    if reading.kind not in VERDICT_KINDS:
        replay = ReplayVerdict("unavailable", reason="ESBMC produced no verdict to validate")
    elif result["target_preserved"]:
        program = Program(_without_esbmc_imports(harness), 0,
                          tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes})), (),
                          (target.lineno, target.end_lineno))
        replay = concrete_replay(program, target.name, seeds=seeds)
    else:
        # ESBMC checked a simplified body; only the original body, fed ESBMC's own values, can confirm.
        replay = _replay_original(harness, target, original, original_target, h.suspect_expression, seeds)
        result["replayed_original_body"] = True
    result["replay"] = replay.to_dict()
    verdict = final_verdict(reading, replay)
    if not result["target_preserved"] and verdict == CONFIRMED:
        verdict = CONFIRMED_SIMPLIFIED
    return verdict, reading.message


def _first_line(node: ast.FunctionDef) -> int:
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def _replay_original(harness: str, target: ast.FunctionDef, original: str, original_target: ast.FunctionDef | None,
                     expression: str, seeds: dict[str, list]) -> ReplayVerdict:
    """Replay the agent's harness with its simplified target swapped back for the original function."""
    if original_target is None:
        return ReplayVerdict("unavailable", reason="original function not found")
    first = _first_line(target)
    source = "\n".join(original.splitlines()[_first_line(original_target) - 1:original_target.end_lineno])
    body = textwrap.indent(textwrap.dedent(source), " " * target.col_offset).splitlines()
    lines = harness.splitlines()
    spliced = "\n".join([*lines[:first - 1], *body, *lines[target.end_lineno:]]) + "\n"
    def_line = first + original_target.lineno - _first_line(original_target)
    try:
        tree = ast.parse(spliced)
    except SyntaxError as exc:
        return ReplayVerdict("unavailable", reason=f"original body does not fit the harness: {exc.msg}")
    swapped = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.lineno == def_line)
    nodes = expression_nodes(swapped, expression)
    if not nodes:
        return ReplayVerdict("unavailable", reason="suspect expression missing from the original function")
    program = Program(_without_esbmc_imports(spliced), 0,
                      tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes})), (),
                      (swapped.lineno, swapped.end_lineno))
    return concrete_replay(program, swapped.name, seeds=seeds, seeds_only=True)


# Engine verdicts the agent is worth trying on: no ESBMC verdict, and something a harness could change.
AGENT_VERDICTS = frozenset({"UNSUPPORTED", "MISSING_DEPENDENCY", "ESBMC_ERROR", "PIPELINE_ERROR", "SPEC_FAILED"})


def run_agent_fallback(results: list[dict], *, run_agent: RunAgent, work_dir: Path, esbmc_command: list[str],
                       bound: int, timeout_seconds: int, agent_timeout: int, sources: Path | None,
                       state: dict, save: Callable[[], None], config: dict, skill: bool = True) -> list[dict]:
    """Run the agent on every engine result without an ESBMC verdict; ``state`` keeps finished cases
    for resuming, and is cleared when ``config`` differs from the run that filled it."""
    from .loop import verification_source  # loop imports this module's siblings; keep the edge one-way

    if state.get("agent_config") != config:
        state["agent_config"], state["agent_results"] = config, {}
    done = state.setdefault("agent_results", {})
    pending = [r for r in results if r["verdict"] in AGENT_VERDICTS]
    print(f"\nAgente: {len(pending)} hipótese(s) sem veredito do ESBMC no motor")
    for index, result in enumerate(pending, 1):
        h = BugHypothesis(**{k: v for k, v in result["hypothesis"].items() if k != "hypothesis_id"})
        if h.hypothesis_id in done:
            continue
        print(f"[agente {index}/{len(pending)}] {Path(h.file).name}::{h.function}", flush=True)
        try:
            data = run_agent_arm(h, work_dir=work_dir, run_agent=run_agent, esbmc_command=esbmc_command,
                                 bound=bound, timeout_seconds=timeout_seconds, agent_timeout=agent_timeout,
                                 source_path=verification_source(h, sources), skill=skill,
                                 notes=None if skill else NOTES_PATH)
        except Exception as exc:  # noqa: BLE001 - one broken case must not end the run
            data = {"hypothesis": h.to_dict(), "verdict": AGENT_FAILED, "reason": f"{type(exc).__name__}: {exc}"}
        data["engine_verdict"] = result["verdict"]
        print(f"    -> {data['verdict']} {data['reason'][:100]}", flush=True)
        done[h.hypothesis_id] = data
        save()
    wanted = {r["hypothesis"]["hypothesis_id"] for r in pending}
    return [data for key, data in done.items() if key in wanted]


_DEFAULT_MODELS = {"openai": "gpt-4o-mini", "google": "gemini-2.5-flash", "ollama": "qwen2.5-coder:7b",
                   "claude_cli": "sonnet"}
_DEFAULT_URLS = {"google": "https://generativelanguage.googleapis.com/v1beta/openai/",
                 "ollama": "http://localhost:11434/v1"}


def make_agent(backend: str, *, model: str | None, esbmc: str, bound: int, plugin: bool = True,
               isolated: bool = True, rounds: int = 8, base_url: str | None = None) -> tuple[RunAgent, bool]:
    """The agent for ``backend``: "claude" is Claude Code with the ESBMC plugin; any LLMClient backend
    (openai, google, ollama, claude_cli) runs the API loop. Returns it and whether the prompt may name
    the plugin's skill (only Claude Code has it)."""
    if backend == "claude":
        return claude_agent(model=model, esbmc=esbmc, plugin=plugin, isolated=isolated), plugin
    from .llm_client import LLMClient  # only the API agent needs a client (and its key)

    url = base_url or _DEFAULT_URLS.get(backend)
    llm = LLMClient(backend=backend, model=model or _DEFAULT_MODELS[backend], **({"base_url": url} if url else {}),
                    request_delay=4.0 if backend == "google" else 0.0)  # Gemini's free tier limits requests/minute
    return api_agent(llm, rounds=rounds, esbmc=esbmc, bound=bound), False
