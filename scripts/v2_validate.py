"""Validate a finished V2 run without the LLM: preservation (V1), reachability of safe verdicts (V2)
and mutation (V3). Writes <run>/validation.json.

  python scripts/v2_validate.py artifacts/v2/<run> [--control <fixed report.json>] [--mutants]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.validation import validate_results  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--control", default=None, help="report of the same hypotheses on the fixed versions")
    parser.add_argument("--mutants", action="store_true")
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    run = Path(args.run)
    results = json.loads((run / "v2_verify_report.json").read_text(encoding="utf-8"))["results"]
    control = json.loads(Path(args.control).read_text(encoding="utf-8"))["results"] if args.control else None
    report = validate_results(results, sources=Path(args.sources), esbmc=args.esbmc, timeout_seconds=args.timeout,
                              work_dir=run / "validation", control=control, with_mutants=args.mutants)
    (run / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
