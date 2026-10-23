"""Pick the fixed sample the rule engine and the agent harness are compared on.

Keeps only hypotheses that name a bug's function and cause or crash site and expect an exception
(no value oracle), then draws one hypothesis per bug and the bugs themselves by a seeded hash,
so the sample is reproducible and nobody chooses a case.

Usage:
  python scripts/v2_harness_sample.py artifacts/v2/final-2026-10-17/v2_verify_report.json \
      --size 30 --seed 20261022 --out dataset/bugs_reais/amostra_harness.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402
from research_pipeline.verify.hypothesis import VALUE_ORACLE  # noqa: E402


def _rank(seed: int, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def harness_sample(results: list[dict], items: dict[str, dict], size: int, seed: int) -> list[dict]:
    by_bug: dict[str, dict[str, dict]] = {}
    for result in results:
        h = result["hypothesis"]
        bug = Path(h["file"]).stem
        item = items.get(bug)
        if item is None or h.get("oracle") == VALUE_ORACLE or not at_bug_line(h, item):
            continue
        by_bug.setdefault(bug, {}).setdefault(h["hypothesis_id"], h)
    picked = []
    for bug in sorted(by_bug, key=lambda b: _rank(seed, b))[:size]:
        chosen = min(by_bug[bug], key=lambda hid: _rank(seed, hid))
        picked.append({**by_bug[bug][chosen], "bug": bug})
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = json.loads(Path(args.report).read_text(encoding="utf-8"))["results"]
    items = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))["items"]
    hypotheses = harness_sample(results, {i["id"]: i for i in items}, args.size, args.seed)
    Path(args.out).write_text(json.dumps({
        "seed": args.seed, "size": len(hypotheses), "source_run": args.report, "rule": __doc__.split("\n\n")[1].replace("\n", " "),
        "hypotheses": hypotheses}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(hypotheses)} hipoteses -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
