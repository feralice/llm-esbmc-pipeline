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
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.agent_arm import claude_agent, run_agent_arm  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402
from research_pipeline.verify.loop import verification_source  # noqa: E402

DEFAULT_VERDICTS = "UNSUPPORTED,MISSING_DEPENDENCY,ESBMC_ERROR,PIPELINE_ERROR,SPEC_FAILED"


def _results(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "results" in data:
        return data["results"]
    return [data["verify_results"][k] for k in sorted(data.get("verify_results", {}), key=int)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="v2_verify_report.json or v2_checkpoint.json")
    parser.add_argument("--verification-sources", default="dataset/v2_real_world/detection_full")
    parser.add_argument("--verdicts", default=DEFAULT_VERDICTS)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--reason", default="", help="only results whose reason matches this regex")
    parser.add_argument("--out", required=True)
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--model", default=None)
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--agent-timeout", type=int, default=900)
    args = parser.parse_args()

    wanted = set(args.verdicts.split(","))
    seen: set[str] = set()
    hypotheses = []
    for item in _results(Path(args.report)):
        h = BugHypothesis(**{k: v for k, v in item["hypothesis"].items() if k != "hypothesis_id"})
        if (item["verdict"] in wanted and h.hypothesis_id not in seen
                and re.search(args.reason, item.get("reason", ""))):
            seen.add(h.hypothesis_id)
            hypotheses.append((h, item["verdict"]))
    if args.limit:
        hypotheses = hypotheses[:args.limit]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "agent_results.json"
    done = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    finished = {r["hypothesis"]["hypothesis_id"] for r in done}
    agent = claude_agent(model=args.model, esbmc=args.esbmc)
    sources = Path(args.verification_sources) if args.verification_sources else None
    for index, (h, previous) in enumerate(hypotheses, 1):
        if h.hypothesis_id in finished:
            continue
        print(f"[{index}/{len(hypotheses)}] {Path(h.file).name}::{h.function} (engine: {previous})", flush=True)
        result = run_agent_arm(h, work_dir=out / "cases", run_agent=agent, esbmc_command=[args.esbmc],
                               bound=args.bound, timeout_seconds=args.timeout, agent_timeout=args.agent_timeout,
                               source_path=verification_source(h, sources))
        result["engine_verdict"] = previous
        print(f"    -> {result['verdict']} preserved={result['target_preserved']} {result['reason'][:100]}", flush=True)
        done.append(result)
        results_path.write_text(json.dumps(done, indent=2), encoding="utf-8")
    print("\n", dict(Counter(r["verdict"] for r in done)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
