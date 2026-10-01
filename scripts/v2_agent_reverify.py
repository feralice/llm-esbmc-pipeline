"""Re-check the harnesses an agent-arm run already wrote, without calling the agent again.

Same rule as the run itself (ESBMC re-run, CPython replay, target body compared with the original);
only the current pipeline code changes, so a harness-side fix is measured at no agent cost.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.agent_arm import AGENT_FAILED, evaluate_harness
from research_pipeline.verify.hypothesis import BugHypothesis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="agent-arm output directory (agent_results.json + cases/)")
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run = Path(args.run)
    rows = []
    for item in json.loads((run / "agent_results.json").read_text(encoding="utf-8")):
        h = BugHypothesis(**{k: v for k, v in item["hypothesis"].items() if k != "hypothesis_id"})
        case_dir = run / "cases" / item["hypothesis"]["hypothesis_id"]
        harness, original = case_dir / "harness.py", case_dir / "original.py"
        result: dict = {}
        if harness.exists() and original.exists():
            verdict, reason = evaluate_harness(
                h, harness.read_text(encoding="utf-8", errors="replace"),
                original.read_text(encoding="utf-8", errors="replace"), case_dir, result,
                esbmc_command=[args.esbmc], bound=args.bound, timeout_seconds=args.timeout,
                output_dir=Path(args.out).with_suffix("") / item["hypothesis"]["hypothesis_id"])
        else:
            verdict, reason = AGENT_FAILED, "no saved harness"
        rows.append({"hypothesis": item["hypothesis"], "verdict": verdict, "id": item["hypothesis"]["hypothesis_id"],
                     "file": Path(h.file).name, "function": h.function,
                     "before": item["verdict"], "after": verdict, "reason": reason[:300],
                     "target_preserved": result.get("target_preserved"), "replay": result.get("replay", {})})
        print(f"{rows[-1]['file']:16s} {item['verdict']:16s} -> {verdict:16s} {reason[:80]}", flush=True)
    print("\n", dict(Counter(r["after"] for r in rows).most_common()))
    Path(args.out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
