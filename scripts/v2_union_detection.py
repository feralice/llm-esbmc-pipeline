"""Union of several detection-only runs (variant A4): a finding sent by any run counts as sent.

  python scripts/v2_union_detection.py <run1> <run2> <run3> --out <union.json>
With one run it evaluates that run; --sample limits every run to the files of a fixed sample, so a
full run and a sample run are compared on the same bugs.
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


def _local(path: str) -> str:
    """The same dataset file whichever checkout (main folder or a worktree) the run was made in."""
    text = str(path)
    start = text.find("dataset/")
    return str(Path(text[start:] if start >= 0 else text).resolve())


def evaluated_sources(reports: list[dict], *, sample: list[str] | None = None) -> list[str]:
    """Files every run analysed (and in the sample, when given)."""
    seen = [{_local(p) for p in r["config"]["input_files"]} for r in reports]
    if sample is not None:
        seen.append({_local(p) for p in sample})
    return sorted(set.intersection(*seen))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--sample", default=None, help="JSON with the sample's 'files' (v2_detection_sample.py)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    reports = [json.loads((Path(r) / "v2_verify_report.json").read_text(encoding="utf-8")) for r in args.runs]
    sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))["files"] if args.sample else None
    sources = evaluated_sources(reports, sample=sample)
    sent, held = union(reports)
    sent = [c for c in sent if _local(c.file) in sources]
    held = [h for h in held if _local(h["file"]) in sources]
    evaluation = evaluate_detection(candidates=sent, ground_truth_path=args.ground_truth,
                                    evaluated_sources=sources, rejected_findings=held)
    Path(args.out).write_text(json.dumps({"runs": args.runs, "sent": len(sent), "held": len(held),
                                          "evaluation": evaluation}, indent=2), encoding="utf-8")
    print(json.dumps({"sent": len(sent), "held": len(held)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
