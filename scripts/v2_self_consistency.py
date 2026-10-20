"""Self-consistency over repeated detection runs (Wang et al., ICLR 2023): keep a hypothesis when at least
``k`` of the ``n`` runs propose it. Two hypotheses are the same when they name the same file, function and
suspect expression (after undoing the prompt rename and normalising whitespace). Reports, for every k, the
bugs at the line, the hypotheses kept and the precision, plus each run alone.

    python scripts/v2_self_consistency.py artifacts/v2/det-2026-10-20-sc1-A1,A2 artifacts/v2/det-2026-10-20-sc2-A1,A2 ...
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402
from research_pipeline.verify.hypothesis import undo_prompt_rename  # noqa: E402


def hypotheses(run: Path, sample: set[str]) -> dict[tuple, dict]:
    """Distinct hypotheses of one run, keyed by (bug, function, expression)."""
    units = json.loads((run / "v2_checkpoint.json").read_text(encoding="utf-8"))["detection_units"]
    found = {}
    for unit in units.values():
        for candidate in unit.get("candidates", []):
            bug = Path(candidate["file"]).stem
            if bug not in sample:
                continue
            expression = undo_prompt_rename(candidate["expression"], candidate["function"])
            key = (bug, candidate["function"], " ".join(expression.split()))
            found[key] = {"function": candidate["function"], "suspect_expression": expression}
    return found


def vote(runs: list[dict[tuple, dict]], items: dict, k: int) -> dict:
    counts: dict[tuple, int] = defaultdict(int)
    merged: dict[tuple, dict] = {}
    for run in runs:
        for key, hypothesis in run.items():
            counts[key] += 1
            merged[key] = hypothesis
    kept = [key for key, count in counts.items() if count >= k]
    at_line = [key for key in kept if at_bug_line(merged[key], items[key[0]])]
    return {"k": k, "kept": len(kept), "bugs_at_line": len({key[0] for key in at_line}),
            "precision": len(at_line) / len(kept) if kept else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--sample", default="dataset/bugs_reais/amostra_deteccao.json")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    args = parser.parse_args()
    items = {i["id"]: i for i in json.loads((ROOT / args.ground_truth).read_text(encoding="utf-8"))["items"]}
    sample = {Path(f).stem for f in json.loads((ROOT / args.sample).read_text(encoding="utf-8"))["files"]}
    sample = {b for b in sample if "behaviour_change" not in items[b]}
    runs = [hypotheses(run, sample) for run in args.runs]
    print(f"denominador: {len(sample)} bugs")
    for path, run in zip(args.runs, runs):
        print(path.name, vote([run], items, 1))
    for k in range(1, len(runs) + 1):
        print(f"{k} de {len(runs)}", vote(runs, items, k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
