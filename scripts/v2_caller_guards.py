"""Count the dataset cases whose callers guard an argument at every call site (caller_facts.caller_guards).
Offline: grounding and the call graph only, no LLM and no ESBMC.

  python scripts/v2_caller_guards.py --out artifacts/v2/caller-guards-2026-11-05.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.caller_facts import collect_facts  # noqa: E402
from research_pipeline.verify.grounding import GroundingFailure, ground  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402


def case_guards(item: dict, sources: Path) -> dict:
    path = sources / item["file"]
    h = BugHypothesis(str(path), item["function"], item.get("expression", ""))
    if not path.exists():
        return {"id": item["id"], "status": "no_source"}
    source = path.read_text(encoding="utf-8", errors="replace")
    grounded = ground(h, source)
    if isinstance(grounded, GroundingFailure):
        return {"id": item["id"], "status": "not_grounded"}
    facts = collect_facts(h, grounded, source)
    return {"id": item["id"], "status": "grounded", "call_sites": facts.site_count,
            "used_as_value": bool(facts.references), "guards": [f"{p}: {form}" for p, form in facts.guards]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    items = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))["items"]
    rows = [case_guards(item, Path(args.sources)) for item in items]
    grounded = [r for r in rows if r["status"] == "grounded"]
    summary = {"cases": len(rows), "status": dict(Counter(r["status"] for r in rows)),
               "with_call_sites": sum(r["call_sites"] > 0 for r in grounded),
               "with_assume": sum(bool(r["guards"]) for r in grounded),
               "forms": dict(Counter(g.split(": ", 1)[1] for r in grounded for g in r["guards"])),
               "cases_with_assume": [r["id"] for r in grounded if r["guards"]]}
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
