"""Union of several detection-only runs (variant A4): a finding sent by any run counts as sent.

  python scripts/v2_union_detection.py <run1> <run2> <run3> --out <union.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import evaluate_detection  # noqa: E402
from research_pipeline.verify.candidate import Candidate  # noqa: E402


def _key(item: dict) -> tuple[str, str, str]:
    return str(Path(item["file"]).resolve()), item["function"], item.get("expression", "")


def union(reports: list[dict]) -> tuple[list[Candidate], list[dict]]:
    sent: dict = {}
    held: dict = {}
    for report in reports:
        for item in report["detection"]["candidates"]:
            sent.setdefault(_key(item), item)
        for item in report["detection"]["rejected_findings"]:
            held.setdefault(_key(item), item)
    return [Candidate.from_dict(i) for i in sent.values()], [i for k, i in held.items() if k not in sent]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    reports = [json.loads((Path(r) / "v2_verify_report.json").read_text(encoding="utf-8")) for r in args.runs]
    sent, held = union(reports)
    sources = sorted({str(Path(p).resolve()) for r in reports for p in r["config"]["input_files"]})
    evaluation = evaluate_detection(candidates=sent, ground_truth_path=args.ground_truth,
                                    evaluated_sources=sources, rejected_findings=held)
    Path(args.out).write_text(json.dumps({"runs": args.runs, "sent": len(sent), "held": len(held),
                                          "evaluation": evaluation}, indent=2), encoding="utf-8")
    print(json.dumps({"sent": len(sent), "held": len(held)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
