"""Add an approved rule to the repair notebook. Run only after the researcher said yes to the rule.

    python scripts/add_repair.py --title "..." --error "ERROR: ..." --what "..." --case "<id> (<bug>), round N"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.lessons import NOTEBOOK, add_repair


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("title", "error", "what", "case"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--notebook", type=Path, default=NOTEBOOK)
    args = parser.parse_args()
    try:
        add_repair(args.title, args.error, args.what, args.case, path=args.notebook, today=date.today())
    except ValueError as exc:
        print(f"Regra recusada: {exc}", file=sys.stderr)
        return 1
    print(f"Regra gravada em {args.notebook}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
