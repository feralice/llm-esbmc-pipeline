"""Compare agent variants (plugin on/off, notes, model) on the hypotheses they all ran.

  python3 scripts/v2_agent_compare.py com_plugin=<dir>/agent_results.json sem_plugin=<dir>/agent_results.json
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.outcome import CHECKED  # noqa: E402


def main() -> int:
    runs = {}
    for arg in sys.argv[1:]:
        label, _, path = arg.partition("=")
        runs[label] = {r["hypothesis"]["hypothesis_id"]: r for r in json.loads(Path(path).read_text(encoding="utf-8"))}
    if len(runs) < 2:
        print(__doc__)
        return 2
    common = set.intersection(*(set(r) for r in runs.values()))
    print(f"{len(common)} hipóteses em comum")
    print(f"{'variante':14s} {'veredito':>8s} {'confirm.':>8s} {'simplif.':>8s} {'alterou':>8s} {'falhou':>7s} "
          f"{'min (mediana)':>14s}")
    for label, results in runs.items():
        rows = [results[k] for k in common]
        kept = [r for r in rows if r.get("target_preserved") is not False]
        verdict = sum(1 for r in kept if r["verdict"] in CHECKED)
        confirmed = sum(1 for r in kept if r["verdict"] == "CONFIRMED")
        simplified = sum(1 for r in rows if r["verdict"] == "CONFIRMED_SIMPLIFIED")
        rewrote = sum(1 for r in rows if r.get("target_preserved") is False)
        failed = sum(1 for r in rows if r["verdict"] == "AGENT_FAILED")
        minutes = statistics.median(r.get("seconds", 0) for r in rows) / 60 if rows else 0
        print(f"{label:14s} {verdict:8d} {confirmed:8d} {simplified:8d} {rewrote:8d} {failed:7d} {minutes:14.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
