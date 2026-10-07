"""Run the harness orchestrator on a finished verify report (no detection LLM call).

Each result runs the arms its stop reason routes to (verify/routing.py); FUZZ_FOUND is dynamic
evidence and is counted apart from CONFIRMED.

  python scripts/v2_orchestrate.py artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json \
      --only-file dataset/bugs_reais/conjunto_dificil.json --arms dynamic --out artifacts/v2/orq-...
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402
from research_pipeline.verify.agent_arm import make_agent, run_agent_arm  # noqa: E402
from research_pipeline.verify.dynamic import FUZZ_FOUND, dynamic_check  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402
from research_pipeline.verify.loop import verification_source  # noqa: E402
from research_pipeline.verify.orchestrator import orchestrate  # noqa: E402

_FORMAL = {"CONFIRMED", "NOT_CONFIRMED", "ESBMC_MISSED"}


def summarize(rows: list[dict], results: list[dict], ground_truth: dict) -> dict:
    by_id = {r["hypothesis"]["hypothesis_id"]: r["hypothesis"] for r in results}

    def at_bug(row: dict) -> bool:
        h = by_id[row["hypothesis_id"]]
        item = ground_truth.get(Path(h["file"]).stem)
        return item is not None and at_bug_line(h, item)

    return {"final": dict(Counter(r["final"] for r in rows)),
            "confirmed_at_bug": sum(r["final"] == "CONFIRMED" and at_bug(r) for r in rows),
            "fuzz_found_at_bug": sum(r["final"] == FUZZ_FOUND and at_bug(r) for r in rows)}


def agent_outcome(data: dict) -> dict:
    """A verdict on a body the agent rewrote says nothing about the original function."""
    if data["verdict"] in _FORMAL and data.get("target_preserved") is False:
        return {**data, "verdict": "TARGET_ALTERED"}
    return data


def _agent_arm(backend: str, args: argparse.Namespace):
    agent, skill = make_agent(backend, model=args.agent_model, esbmc=args.esbmc, bound=args.bound)
    sources = Path(args.verification_sources)

    def run(result: dict) -> dict:
        h = BugHypothesis(**{k: v for k, v in result["hypothesis"].items() if k != "hypothesis_id"})
        data = run_agent_arm(h, work_dir=Path(args.out) / f"{backend}_cases", run_agent=agent,
                             esbmc_command=[args.esbmc], bound=args.bound, timeout_seconds=args.timeout,
                             agent_timeout=args.agent_timeout, source_path=verification_source(h, sources),
                             skill=skill)
        return agent_outcome(data)
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--only-file", default=None, help="JSON with 'ids' (v2_hard_set.py)")
    parser.add_argument("--arms", default="dynamic", help="subset of dynamic,api_agent,claude_agent")
    parser.add_argument("--api-backend", default="claude_cli", help="LLMClient backend of the API agent")
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--verification-sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = json.loads(Path(args.report).read_text(encoding="utf-8"))["results"]
    if args.only_file:
        wanted = set(json.loads(Path(args.only_file).read_text(encoding="utf-8"))["ids"].split(","))
        results = [r for r in results if r["hypothesis"]["hypothesis_id"] in wanted]
    builders = {"dynamic": lambda: dynamic_check,
                "api_agent": lambda: _agent_arm(args.api_backend, args),
                "claude_agent": lambda: _agent_arm("claude", args)}
    arms = {name: builders[name]() for name in args.arms.split(",")}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "orchestrator_state.json"
    config = {"report": args.report, "only_file": args.only_file, "arms": sorted(arms),
              "api_backend": args.api_backend, "agent_model": args.agent_model, "bound": args.bound,
              "timeout": args.timeout}
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if state.get("config") != config:
        state = {"config": config}

    def save() -> None:
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    rows = orchestrate(results, arms=arms, state=state, save=save)
    items = {i["id"]: i for i in json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))["items"]}
    summary = summarize(rows, results, items)
    (out / "orchestrated.json").write_text(json.dumps({"config": config, "rows": rows, "summary": summary},
                                                      indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
