"""Build the optional manual-baseline subset from the full V2 corpus.

Usage: python scripts/build_v2_eligible.py
The full corpus remains dataset/bugs_reais; this command only materializes
the cases whose reference harnesses are already ESBMC-verifiable.
It fails listing every gate an item explicitly marked eligible does not pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_eligibility import (
    EligibilityError,
    build_eligible,
)


def main() -> int:
    try:
        summary = build_eligible(ROOT / "dataset" / "bugs_reais", ROOT / "dataset" / "harness_bugs_reais" / "elegiveis_0909")
    except EligibilityError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{len(summary['eligible'])} of {summary['total']} items eligible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
