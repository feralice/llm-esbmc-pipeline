#!/usr/bin/env python3
"""Write <run>/relatorio.md from <run>/agent_results.json: confirmed bugs with their test, what the controls
rejected, and the LLM suspicions grouped by why ESBMC could not decide them.

  python scripts/v2_run_report.py artifacts/v2/<run>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research_pipeline.verify.run_report import render_run_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", help="folder with agent_results.json")
    args = parser.parse_args(argv)
    run = Path(args.run)
    results = json.loads((run / "agent_results.json").read_text(encoding="utf-8"))
    (run / "relatorio.md").write_text(render_run_report(results), encoding="utf-8")
    print(run / "relatorio.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
