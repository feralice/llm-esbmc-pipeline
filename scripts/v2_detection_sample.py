"""Pick the fixed sample that detection prompt variants are compared on.

Keeps the dataset's proportion of failure kinds (largest remainder), skips the patch-context items,
and orders each kind by a hash of the id, so the sample is reproducible and nobody chooses a case.

Usage:
  python scripts/v2_detection_sample.py --size 50 --out dataset/bugs_reais/amostra_deteccao.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sample(items: list[dict], *, size: int, excluded: set[str]) -> list[dict]:
    by_kind: dict[str, list[dict]] = {}
    for item in items:
        if item["id"] not in excluded:
            by_kind.setdefault(item["failure_kind"], []).append(item)
    total = sum(len(v) for v in by_kind.values())
    quota = {k: size * len(v) / total for k, v in by_kind.items()}
    counts = {k: int(q) for k, q in quota.items()}
    for kind in sorted(quota, key=lambda k: (counts[k] - quota[k], k))[:size - sum(counts.values())]:
        counts[kind] += 1
    picked = []
    for kind in sorted(by_kind):
        ordered = sorted(by_kind[kind], key=lambda i: hashlib.sha256(i["id"].encode()).hexdigest())
        picked.extend(ordered[:counts[kind]])
    return picked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="dataset/bugs_reais/manifest.json")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--size", type=int, default=50)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    kinds = {i["id"]: i["failure_kind"]
             for i in json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))["items"]}
    files = {i["id"]: i["detection_file"] for i in manifest["items"]}
    excluded = set(manifest.get("evaluation_policy", {}).get("patch_context_items", []))
    picked = sample([{"id": k, "failure_kind": v} for k, v in kinds.items()], size=args.size, excluded=excluded)
    base = Path(args.manifest).parent
    Path(args.out).write_text(json.dumps({
        "rule": __doc__.split("\n\n")[1].replace("\n", " "),
        "files": [str(base / files[i["id"]]) for i in picked], "cases": picked}, indent=2) + "\n", encoding="utf-8")
    print(f"{len(picked)} bugs -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
