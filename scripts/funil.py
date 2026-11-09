"""Where each labelled bug stops: detection, ESBMC verdict, confirmation. One row per bug, best verdict wins.

    python scripts/funil.py RUN_DIR GROUND_TRUTH [--against OLD_RUN_DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from calibrate_review import label_hypotheses

RANK = ["CONFIRMED", "NOT_CONFIRMED", "BOUND_INCONCLUSIVE", "ESBMC_MISSED", "OTHER_FAILURE", "UNVALIDATED",
        "ESBMC_TIMEOUT", "ESBMC_ERROR", "SPEC_FAILED", "LLM_ONLY"]


def best_verdicts(run: Path, items: list[dict]) -> dict[str, tuple[str, str]]:
    report = json.loads((run / "v2_verify_report.json").read_text())
    results = report["results"]
    candidates = [{"file": r["hypothesis"]["file"], "function": r["hypothesis"]["function"],
                   "expression": r["hypothesis"]["suspect_expression"]} for r in results]
    best: dict[str, tuple[str, str]] = {}
    for result, bug in zip(results, label_hypotheses(candidates, items)):
        verdict = result["verdict"] if result["verdict"] in RANK else "LLM_ONLY"
        if bug and (bug not in best or RANK.index(verdict) < RANK.index(best[bug][0])):
            best[bug] = (verdict, str(result.get("reason", ""))[:70])
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir")
    parser.add_argument("ground_truth")
    parser.add_argument("--against")
    args = parser.parse_args()
    payload = json.loads(Path(args.ground_truth).read_text())
    items = payload if isinstance(payload, list) else payload.get("items") or list(payload.values())
    new = best_verdicts(Path(args.run_dir), items)
    old = best_verdicts(Path(args.against), items) if args.against else {}
    print(f"Bugs com hipótese certa: {len(new)} de {len(items)}")
    print("Onde pararam:", dict(Counter(v for v, _ in new.values())))
    if old:
        print(f"Antes: {len(old)} com hipótese; {dict(Counter(v for v, _ in old.values()))}")
    for bug in sorted(set(new) | set(old)):
        before, now = old.get(bug, ("-", ""))[0], new.get(bug, ("sem hipótese", ""))[0]
        mark = "  <- subiu" if RANK.index(now if now in RANK else "LLM_ONLY") < RANK.index(before if before in RANK else "LLM_ONLY") \
            and before != "-" else ""
        print(f"{bug:24} {before:18} -> {now:18}{mark}")
    missing = [i["id"] for i in items if i["id"] not in new]
    print("Sem hipótese certa:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
