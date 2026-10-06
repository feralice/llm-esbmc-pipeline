"""Pick the fixed set of hard cases that harness changes are measured on.

A case is a hypothesis of a finished run that points at the ground-truth bug line (cause or crash
site) of its function: detection already succeeded there, so only the harness decides the outcome.
Every case with an ESBMC verdict is kept (regression and vacuity checks); the rest are taken one per
stuck verdict in turn, so no single limit fills the set. Selection uses only the rule, never a case
picked by hand.

Usage:
  python scripts/v2_hard_set.py artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json \
      --out dataset/bugs_reais/conjunto_dificil.json
Then: scripts/v2_replay_specs.py <report> --only <ids from the file> --out ...
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import expressions_equivalent  # noqa: E402

CHECKED = ("CONFIRMED", "NOT_CONFIRMED", "ESBMC_MISSED")


def at_bug_line(hypothesis: dict, item: dict) -> bool:
    if hypothesis["function"] not in {f.strip() for f in item["function"].split("/")}:
        return False
    expected = [e for e in [item.get("expression", ""), *item.get("crash_expressions", [])] if e]
    return any(expressions_equivalent(e, hypothesis["suspect_expression"]) for e in expected)


def hard_set(results: list[dict], ground_truth: dict[str, dict], *, size: int = 20) -> list[dict]:
    cases: dict[str, dict] = {}
    for result in results:
        h = result["hypothesis"]
        item = ground_truth.get(Path(h["file"]).stem)
        if item is not None and h["hypothesis_id"] not in cases and at_bug_line(h, item):
            cases[h["hypothesis_id"]] = {"hypothesis_id": h["hypothesis_id"], "bug": Path(h["file"]).stem,
                                         "function": h["function"], "verdict": result["verdict"]}
    ordered = sorted(cases.values(), key=lambda c: (c["bug"], c["hypothesis_id"]))
    picked = [c for c in ordered if c["verdict"] in CHECKED]
    stuck = {}
    for case in ordered:
        if case["verdict"] not in CHECKED:
            stuck.setdefault(case["verdict"], []).append(case)
    for row in zip_longest(*(stuck[v] for v in sorted(stuck))):
        picked.extend(c for c in row if c is not None)
    return picked[:size]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = json.loads(Path(args.report).read_text(encoding="utf-8"))["results"]
    items = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))["items"]
    cases = hard_set(results, {i["id"]: i for i in items}, size=args.size)
    Path(args.out).write_text(json.dumps({
        "source_report": args.report, "rule": __doc__.split("\n\n")[1].replace("\n", " "),
        "ids": ",".join(c["hypothesis_id"] for c in cases), "cases": cases}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"{len(cases)} casos -> {args.out}")
    for case in cases:
        print(f"  {case['verdict']:20} {case['bug']}::{case['function']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
