"""Pick bugs of dataset/bugs_reais from projects the discipline set does not use, to calibrate the review pass.

Round-robin over projects (shuffled by the seed), so no repository dominates. Writes the id list and an input
folder of links to funcao_com_bug/, ready for ``--input``.

    python scripts/make_review_sample.py --size 100 --out artifacts/review
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def choose(items: list[dict], excluded_projects: set[str], size: int, seed: int) -> list[str]:
    by_project: dict[str, list[str]] = defaultdict(list)
    for item in items:
        project = item["provenance"]["project"]
        if project not in excluded_projects:
            by_project[project].append(item["id"])
    rng = random.Random(seed)
    queues = [rng.sample(ids, len(ids)) for _, ids in sorted(by_project.items())]
    rng.shuffle(queues)
    chosen: list[str] = []
    while queues and len(chosen) < size:
        for queue in list(queues):
            chosen.append(queue.pop())
            if not queue:
                queues.remove(queue)
            if len(chosen) == size:
                break
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    pool = json.loads((ROOT / "dataset/bugs_reais/ground_truths.json").read_text(encoding="utf-8"))["items"]
    discipline = json.loads((ROOT / "dataset/disciplina_pgene601/ground_truths.json").read_text(encoding="utf-8"))["items"]
    excluded = {item["provenance"]["project"] for item in discipline}
    ids = choose(pool, excluded, args.size, args.seed)
    files = {item["id"]: item["file"] for item in pool}
    folder = args.out / f"entrada_v2_{len(ids)}"
    folder.mkdir(parents=True, exist_ok=True)
    for bug in ids:
        link = folder / files[bug]
        if not link.exists():
            link.symlink_to((ROOT / "dataset/bugs_reais/funcao_com_bug" / files[bug]).resolve())
    (args.out / f"amostra_v2_{len(ids)}.json").write_text(json.dumps({"seed": args.seed, "ids": ids}, indent=1))
    projects = {item["provenance"]["project"] for item in pool if item["id"] in set(ids)}
    print(f"{len(ids)} bugs de {len(projects)} projetos; pasta de entrada: {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
