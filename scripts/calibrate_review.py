"""Pick the cut for the hypothesis review pass (``--review-threshold``) from scored hypotheses with a ground truth.

A run with ``--review-threshold 0`` scores every hypothesis and drops none; its checkpoint holds the scores.
The cut is the highest one that keeps at least one hypothesis of every known bug on the calibration side; the
held-out side shows what that cut would have lost. The split is by project, so no repository sits on both sides.

    python scripts/calibrate_review.py \
        --set v2:artifacts/review/v2/v2_checkpoint.json:dataset/bugs_reais/ground_truths.json \
        --set disciplina:artifacts/review/disc/v2_checkpoint.json:dataset/disciplina_pgene601/ground_truths.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research_pipeline.hypothesis_review import cache_key
from research_pipeline.v2_evaluator import expressions_equivalent
from research_pipeline.verify.candidate import Candidate


def label_hypotheses(candidates: list[dict], items: list[dict]) -> list[str | None]:
    """Id of the bug whose file, function and expression a hypothesis matches, or None."""
    labels: list[str | None] = []
    for candidate in candidates:
        name = Path(candidate["file"]).name
        hit = None
        for item in items:
            functions = {f.strip() for f in item["function"].split("/")}
            expected = [e for e in [item.get("expression", ""), *item.get("cause_expressions", []),
                                    *item.get("crash_expressions", [])] if e]
            if (item["file"] == name and candidate["function"] in functions
                    and any(expressions_equivalent(e, candidate["expression"]) for e in expected)):
                hit = item["id"]
                break
        labels.append(hit)
    return labels


def split_by_project(projects: dict[str, str], fraction: float, seed: int) -> tuple[set[str], set[str]]:
    """Whole projects go to the calibration side until it holds ``fraction`` of the bugs."""
    by_project: dict[str, list[str]] = defaultdict(list)
    for bug, project in projects.items():
        by_project[project].append(bug)
    if len(by_project) < 2:
        raise ValueError("need at least two projects to split by project")
    names = sorted(by_project)
    random.Random(seed).shuffle(names)
    calibration: set[str] = set()
    for name in names[:-1]:
        if len(calibration) >= fraction * len(projects):
            break
        calibration.update(by_project[name])
    return calibration, set(projects) - calibration


def choose_threshold(scores: list[float], bug_of: list[str | None]) -> float:
    """Highest cut that keeps one hit of every bug that has a hit."""
    best: dict[str, float] = {}
    for score, bug in zip(scores, bug_of):
        if bug is not None:
            best[bug] = max(best.get(bug, score), score)
    return min(best.values()) if best else 0.0


def table(scores: list[float], bug_of: list[str | None],
          thresholds: list[float]) -> list[tuple[float, int, int, list[str]]]:
    """Per cut: hypotheses kept, bugs still hit, bugs lost (hit at cut 0 but no longer)."""
    found = {bug for bug in bug_of if bug is not None}
    rows = []
    for cut in thresholds:
        kept = [(s, b) for s, b in zip(scores, bug_of) if s >= cut]
        alive = {b for _, b in kept if b is not None}
        rows.append((cut, len(kept), len(alive), sorted(found - alive)))
    return rows


def load_scored(checkpoint_path: Path, ground_truth_path: Path) -> tuple[list[tuple[float, str | None, str]], dict, int]:
    """(score, bug hit, owner bug of the file) per hypothesis, bug id to project, and how many had no clean score."""
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    items = json.loads(ground_truth_path.read_text(encoding="utf-8"))["items"]
    cache = checkpoint.get("review", {}).get("scores", {})
    candidates = [c for unit in checkpoint["detection_units"].values() for c in unit["candidates"]]
    labels = label_hypotheses(candidates, items)
    owner = {item["file"]: item["id"] for item in items}
    scored, missing = [], 0
    for candidate, label in zip(candidates, labels):
        entry = cache.get(cache_key(Candidate.from_dict(candidate)))
        if entry is None or owner.get(Path(candidate["file"]).name) is None:
            missing += 1
            continue
        scored.append((entry["score"], label, owner[Path(candidate["file"]).name]))
    return scored, {i["id"]: i["provenance"]["project"] for i in items}, missing


def _side(name: str, scores: list[float], bugs: list[str | None], threshold: float) -> None:
    rows = table(scores, bugs, sorted({0.0, threshold, *range(1, 11)}))
    print(f"\n{name}: {len(scores)} hipóteses, {len({b for b in bugs if b})} bugs com acerto")
    print("corte  hipóteses  bugs_com_acerto  bugs_perdidos")
    for cut, kept, alive, lost in rows:
        mark = "  <== corte escolhido" if cut == threshold else ""
        print(f"{cut:5.1f}  {kept:9d}  {alive:15d}  {','.join(lost) or '-'}{mark}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", action="append", required=True, metavar="NOME:CHECKPOINT:GABARITO")
    parser.add_argument("--calibration-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    rows: list[tuple[float, str | None, str, str]] = []
    projects: dict[str, str] = {}
    for spec in args.set:
        name, checkpoint, truth = spec.split(":", 2)
        scored, mapping, missing = load_scored(Path(checkpoint), Path(truth))
        print(f"{name}: {len(scored)} hipóteses com nota, {missing} sem nota ou de arquivo sem gabarito (ignoradas)")
        rows += [(score, bug, owner, name) for score, bug, owner in scored]
        projects.update(mapping)
    calibration, held_out = split_by_project({o: projects[o] for _, _, o, _ in rows}, args.calibration_fraction,
                                             args.seed)
    cal = [(s, b) for s, b, o, _ in rows if o in calibration]
    threshold = choose_threshold([s for s, _ in cal], [b for _, b in cal])
    print(f"\nCorte escolhido na calibração ({len(calibration)} bugs): {threshold}")
    _side("calibração", [s for s, _ in cal], [b for _, b in cal], threshold)
    hold = [(s, b) for s, b, o, _ in rows if o in held_out]
    _side("fora da calibração", [s for s, _ in hold], [b for _, b in hold], threshold)
    for set_name in sorted({n for *_, n in rows}):
        part = [(s, b) for s, b, _, n in rows if n == set_name]
        _side(f"conjunto {set_name} (todas as hipóteses)", [s for s, _ in part], [b for _, b in part], threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
