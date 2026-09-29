"""V2 verify-engine smoke run on the V2 ground truth without any LLM call.

Stage 0 (every case): grounding, verbatim slice, placeholder render, undefined names.
Stage 1 (--esbmc): cases that pass stage 0 go through ESBMC + replay with a naive spec
(declared annotations, otherwise int for parameters and list[int] for attributes).
The naive spec is a plumbing check, not a result: real runs use the LLM spec.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.grounding import GroundingFailure, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.loop import precheck, verify_hypothesis
from research_pipeline.verify.spec import InputSpec, resolved_types

DATASET = ROOT / "dataset" / "v2_real_world"


class NaiveSpec:
    model = "naive-offline"

    def __init__(self, grounded):
        params, attrs = resolved_types(InputSpec({}, {}, ()), grounded)
        self.reply = json.dumps({
            "params": {n: "int" for n, t in params.items() if not t},
            "attributes": {n: "list[int]" for n, t in attrs.items() if not t},
            "stubs": {key: "int" for key in grounded.stub_keys},
            "assumptions": [],
        })

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        return SynthResult(harness=self.reply, raw_response="", model=self.model, telemetry={})


def _cases():
    items = json.loads((DATASET / "ground_truths.json").read_text(encoding="utf-8"))["items"]
    for item in items:
        full = DATASET / "detection_full" / item["file"]
        source_path = full if full.exists() else DATASET / "detection" / item["file"]
        function = str(item["function"]).split("/")[0].strip()
        yield item["id"], source_path, BugHypothesis(str(DATASET / "detection" / item["file"]), function,
                                                     str(item.get("expression", "")),
                                                     category=",".join(item.get("categories", [])))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--esbmc", default="", help="ESBMC binary; enables stage 1")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--out", default="outputs/v2_verify_smoke")
    args = parser.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_id, source_path, h in _cases():
        source = source_path.read_text(encoding="utf-8", errors="replace")
        grounded = ground(h, source)
        row = {"id": case_id, "source": source_path.parent.name, "function": h.function}
        if isinstance(grounded, GroundingFailure):
            row.update(verdict="GROUNDING_FAILED", reason=grounded.reason)
        elif args.esbmc and (not args.limit or sum(1 for r in rows if "llm_calls" in r) < args.limit):
            result = verify_hypothesis(h, llm=NaiveSpec(grounded), source=source, esbmc_command=[args.esbmc],
                                       bound=5, timeout_seconds=args.timeout, work_dir=out / "programs",
                                       max_repairs=0)
            data = result.to_dict()
            row.update(verdict=data["verdict"], reason=data["reason"][:200], llm_calls=data["llm_calls"],
                       replay=data["replay"], transforms=data["transforms"])
        else:
            _, verdict, reason = precheck(h, source)
            row.update(verdict=verdict or "READY_FOR_LLM", reason=reason[:200])
        rows.append(row)
        print(f"{case_id:14s} {row['source']:15s} {row['verdict']:20s} {row.get('reason', '')[:90]}")
    counts = Counter(r["verdict"] for r in rows)
    print("\n", dict(counts.most_common()))
    (out / "smoke.json").write_text(json.dumps({"counts": counts, "rows": rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
