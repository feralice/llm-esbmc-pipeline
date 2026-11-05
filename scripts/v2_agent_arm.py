"""Experimental arm: let Claude Code + the ESBMC plugin build harnesses the deterministic engine could not.

Reads a verify-engine report or checkpoint, keeps the hypotheses whose verdict is in --verdicts,
and runs the agent on each one. Every verdict is recomputed by the pipeline (ESBMC + CPython
replay); results are appended to <out>/agent_results.json so the run can be resumed.

Uses the Claude Code subscription (no per-token API cost), one agent session per case.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.agent_arm import (  # noqa: E402
    AGENT_VERDICTS, NOTES_PATH, make_agent, run_agent_arm, session_failed, skill_versions)
from research_pipeline.verification.esbmc_runner import DEFAULT_ESBMC  # noqa: E402
from research_pipeline.verify.esbmc_knowledge import KNOWLEDGE_CACHE, esbmc_root_of, load_index  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402
from research_pipeline.verify.loop import verification_source  # noqa: E402
from research_pipeline.llm.rate_limit import exit_on_usage_limit  # noqa: E402

# Flags added after earlier runs: a result recorded before the flag existed ran with it off.
OFF_BY_DEFAULT = {"graph_tool": False}
COMPARED_FIELDS = ("graph_tool", "fixed_sources", "backend", "plugin", "isolated", "notes", "model", "plugin_command", "allow_simplify",
                   "differential", "pytest", "log_rounds", "esbmc_commit", "skills", "bound", "timeout",
                   "agent_timeout", "retry")
DEFAULT_VERDICTS = ",".join(sorted(AGENT_VERDICTS))


def _results(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "results" in data:
        return data["results"]
    return [data["verify_results"][k] for k in sorted(data.get("verify_results", {}), key=int)]


_BUILD_MARKER = re.compile(rb"ESBMC built from +([0-9a-f]{40})")


def _real_binary(esbmc: str) -> Path:
    path = Path(esbmc).expanduser()
    if path.suffix == ".sh" and path.is_file():
        target = re.search(r"^exec (/\S+)", path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
        if target:
            return Path(target.group(1))
    return path


def build_commit(binary: Path) -> str | None:
    """The commit embedded in the binary itself, read in chunks (the binary is hundreds of MB)."""
    tail = b""
    try:
        with binary.open("rb") as handle:
            while chunk := handle.read(1 << 24):
                found = _BUILD_MARKER.search(tail + chunk)
                if found:
                    return found.group(1).decode()
                tail = chunk[-80:]
    except OSError:
        return None
    return None


def esbmc_identity(esbmc: str) -> dict[str, str | None]:
    """esbmc_commit: the build commit embedded in the binary (None when absent, never guessed from the
    checkout); esbmc_checkout: HEAD of the checkout next to it, so a mismatch is visible."""
    def run(command: list[str]) -> str:
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return done.stdout.strip().splitlines()[0] if done.returncode == 0 and done.stdout.strip() else ""

    root = esbmc_root_of([esbmc])
    return {"esbmc_commit": build_commit(_real_binary(esbmc)),
            "esbmc_checkout": run(["git", "-C", str(root), "rev-parse", "HEAD"]) if root else "",
            "esbmc_version": run([esbmc, "--version"])}


def _hypothesis(stored: dict) -> BugHypothesis:
    return BugHypothesis(**{k: v for k, v in stored.items() if k != "hypothesis_id"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="", help="v2_verify_report.json or v2_checkpoint.json "
                        "(required unless --sample is given)")
    parser.add_argument("--verification-sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--verdicts", default=DEFAULT_VERDICTS)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--reason", default="", help="only results whose reason matches this regex")
    parser.add_argument("--out", required=True)
    parser.add_argument("--esbmc", default=DEFAULT_ESBMC)
    parser.add_argument("--model", default=None)
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--backend", default="claude",
                        choices=["claude", "openai", "google", "ollama", "claude_cli"],
                        help="claude: Claude Code + ESBMC plugin; the others run the same loop through an API "
                             "(OPENAI_API_KEY / GEMINI_API_KEY; ollama runs a local model)")
    parser.add_argument("--rounds", type=int, default=8, help="API backends: harness attempts per case")
    parser.add_argument("--base-url", default=None, help="API backends: endpoint (e.g. http://localhost:11434/v1)")
    parser.add_argument("--no-plugin", action="store_true", help="run the agent without the ESBMC plugin")
    parser.add_argument("--not-isolated", action="store_true",
                        help="load the user's Claude Code settings too (global plugins, hooks); default: isolated")
    parser.add_argument("--plugin-command", choices=["verify", "audit"], default="",
                        help="after the harness is ready, run /esbmc-plugin:<command> on it and keep its report")
    parser.add_argument("--retry", action="store_true",
                        help="one more agent attempt, told why, when the harness never reached the hypothesis "
                             "or changed the target body (the first attempt stays in first_attempt)")
    parser.add_argument("--allow-simplify", action="store_true",
                        help="let the agent simplify constructs ESBMC rejects inside the function; a confirmation "
                             "then needs ESBMC's inputs to break the ORIGINAL body (CONFIRMED_SIMPLIFIED)")
    parser.add_argument("--notes", default="", help="ESBMC-Python notes the agent reads first "
                        "(e.g. src/research_pipeline/verify/esbmc_python_notes.md)")
    parser.add_argument("--project-skills", action="store_true",
                        help="install the project's skills (regras-harness, ...) in each case folder")
    parser.add_argument("--log-rounds", action="store_true", help="record every ESBMC call the agent makes")
    parser.add_argument("--differential", action=argparse.BooleanOptionalAction, default=True,
                        help="differential test of a confirmation against the original (default: on)")
    parser.add_argument("--pytest", action=argparse.BooleanOptionalAction, default=True,
                        help="run ESBMC's generated pytest for a confirmation (default: on)")
    parser.add_argument("--graph-tool", action="store_true",
                        help="install graph.py, the call graph of original.py the agent can query (plan B, item 7)")
    parser.add_argument("--fixed-sources", default="dataset/bugs_reais/arquivo_corrigido",
                        help="fixed versions, one file per buggy file name: the control a confirmation must pass")
    parser.add_argument("--sample", default="", help="fixed sample (e.g. dataset/bugs_reais/amostra_harness.json): "
                        "run exactly its hypotheses, ignoring --verdicts and --reason")
    args = parser.parse_args(argv)

    items = _results(Path(args.report)) if args.report else []
    wanted = set(args.verdicts.split(","))
    hypotheses = []
    if args.sample:
        for stored in json.loads(Path(args.sample).read_text(encoding="utf-8"))["hypotheses"]:
            h = _hypothesis(stored)
            engine = next((i["verdict"] for i in items if _hypothesis(i["hypothesis"]).hypothesis_id == h.hypothesis_id), "")
            hypotheses.append((h, engine))
    elif args.report:
        seen: set[str] = set()
        for item in items:
            h = _hypothesis(item["hypothesis"])
            if (item["verdict"] in wanted and h.hypothesis_id not in seen
                    and re.search(args.reason, item.get("reason", ""))):
                seen.add(h.hypothesis_id)
                hypotheses.append((h, item["verdict"]))
    else:
        parser.error("--report or --sample is required")
    if args.limit:
        hypotheses = hypotheses[:args.limit]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "agent_results.json"
    done = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    finished = {r["hypothesis"]["hypothesis_id"] for r in done if not session_failed(r)}
    variant = {"backend": args.backend, "plugin": not args.no_plugin and args.backend == "claude", "isolated": not args.not_isolated, "notes": args.notes,
               "model": args.model, "plugin_command": args.plugin_command,
               "allow_simplify": args.allow_simplify, "retry": args.retry, "differential": args.differential, "pytest": args.pytest,
               "log_rounds": args.log_rounds, "bound": args.bound, "timeout": args.timeout,
               "agent_timeout": args.agent_timeout, "fixed_sources": args.fixed_sources, "graph_tool": args.graph_tool, **esbmc_identity(args.esbmc),
               "skills": skill_versions() if args.project_skills else {}}
    if variant["esbmc_commit"] is None:
        print("warning: no 'ESBMC built from' string in the binary; this run will not record the ESBMC build commit",
              file=sys.stderr)
    # Every compared field, so a result recorded before a field existed is not taken as agreeing with it.
    differing = sorted({key for r in done for key in COMPARED_FIELDS
                        if variant.get(key) != r.get("variant", {}).get(key, OFF_BY_DEFAULT.get(key))})
    if differing:
        print(f"refusing to resume {results_path}: its results came from another engine; "
              f"differing fields: {', '.join(differing)}", file=sys.stderr)
        return 2
    agent, skill = make_agent(args.backend, model=args.model, esbmc=args.esbmc, bound=args.bound,
                              plugin=not args.no_plugin, isolated=not args.not_isolated, rounds=args.rounds,
                              base_url=args.base_url, log_rounds=args.log_rounds,
                              graph_tool=args.graph_tool)
    notes = Path(args.notes) if args.notes else (None if args.backend == "claude" else NOTES_PATH)
    sources = Path(args.verification_sources) if args.verification_sources else None
    root = esbmc_root_of([args.esbmc]) if args.log_rounds else None
    knowledge = load_index(root, KNOWLEDGE_CACHE) if root is not None else None
    for index, (h, previous) in enumerate(hypotheses, 1):
        if h.hypothesis_id in finished:
            continue
        print(f"[{index}/{len(hypotheses)}] {Path(h.file).name}::{h.function} (engine: {previous})", flush=True)
        fixed = Path(args.fixed_sources) / Path(h.file).name
        fixed = fixed if fixed.is_file() else None
        result = run_agent_arm(h, work_dir=out / "cases", run_agent=agent, esbmc_command=[args.esbmc],
                               bound=args.bound, timeout_seconds=args.timeout, agent_timeout=args.agent_timeout,
                               source_path=verification_source(h, sources), skill=skill,
                               notes=notes, plugin_command=args.plugin_command if args.backend == "claude" else "",
                               allow_simplify=args.allow_simplify, project_skills=args.project_skills,
                               log_rounds=args.log_rounds, differential=args.differential, pytest=args.pytest,
                               knowledge_index=knowledge, retry=args.retry, fixed_path=fixed,
                               graph_tool=args.graph_tool)
        result["engine_verdict"], result["variant"] = previous, variant
        result["fixed_control"] = "ran" if fixed else "missing"
        print(f"    -> {result['verdict']} preserved={result['target_preserved']} {result['reason'][:100]}", flush=True)
        position = next((i for i, r in enumerate(done) if r["hypothesis"]["hypothesis_id"] == h.hypothesis_id), None)
        if position is None:
            done.append(result)
        else:
            done[position] = result
        results_path.write_text(json.dumps(done, indent=2), encoding="utf-8")
    print("\n", dict(Counter(r["verdict"] for r in done)))
    return 0


if __name__ == "__main__":
    raise SystemExit(exit_on_usage_limit(main))
