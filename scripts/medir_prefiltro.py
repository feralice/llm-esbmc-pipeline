"""Mede o pré-filtro (scan/prefilter.py) em relatórios de scan já gravados: sem chamada de LLM.

Uso: python scripts/medir_prefiltro.py RELATORIO_scan_report.json [...]
Imprime, por veredito, quantas hipóteses o filtro derrubaria e o motivo. Hipóteses CONFIRMED ou
reproduzidas em CPython que caem são perdas de recall e aparecem em destaque.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from research_pipeline.scan.prefilter import drop_reason  # noqa: E402


def _source(root: Path, file: str) -> str:
    path = Path(file)
    for candidate in (path, root / path.name, root / file.lstrip("/")):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")
    return ""


def measure(report_path: Path) -> list[dict]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    root = Path(report.get("config", {}).get("root", "."))
    rows = []
    for result in report.get("results", []):
        h = result["hypothesis"]
        reason = drop_reason(h.get("suspect_expression", ""), h.get("trigger_condition", ""),
                             _source(root, h["file"]), h["function"])
        rows.append({"report": report_path.parent.name, "function": h["function"], "verdict": result["verdict"],
                     "reason": reason})
    return rows


def main(paths: list[str]) -> int:
    rows = [row for p in paths for row in measure(Path(p))]
    by_verdict = Counter(r["verdict"] for r in rows)
    dropped = Counter(r["verdict"] for r in rows if r["reason"])
    print(f"hipóteses: {len(rows)}; derrubadas: {sum(dropped.values())}")
    for verdict, total in sorted(by_verdict.items()):
        print(f"  {verdict}: {dropped.get(verdict, 0)}/{total}")
    for r in rows:
        if r["reason"]:
            print(f"- [{r['verdict']}] {r['report']} {r['function']}: {r['reason']}")
    lost = [r for r in rows if r["reason"] and r["verdict"] == "CONFIRMED"]
    print(f"CONFIRMED perdidos: {len(lost)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
