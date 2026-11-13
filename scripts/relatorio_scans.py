"""Raw summary of scan folders for the morning triage: verdict counts and the hypotheses worth reading.

    python scripts/relatorio_scans.py PASTA [PASTA ...] --out relatorio.md

No judgement here: CONFIRMED and other checked verdicts are listed with their trigger so that a person reads the
real code before calling anything a bug. LLM_ONLY (repair rounds ran out) is only counted.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

LISTED = ("CONFIRMED", "VALUE_CONFIRMED", "UNVALIDATED", "OTHER_FAILURE", "ESBMC_MISSED", "BOUND_INCONCLUSIVE")


def _results(folder: Path) -> list[dict]:
    report = folder / "scan_report.json"
    if report.exists():
        return json.loads(report.read_text(encoding="utf-8")).get("results", [])
    checkpoint = folder / "scan_checkpoint.json"
    if checkpoint.exists():
        return list(json.loads(checkpoint.read_text(encoding="utf-8")).get("verify_results", {}).values())
    return []


def summarize(folders: list[Path]) -> str:
    lines = ["# Scans: resumo bruto", "",
             "Nada aqui é achado confirmado. Cada hipótese listada precisa de leitura do código real e reprodução "
             "fora do harness antes de virar issue.", ""]
    for folder in folders:
        results = _results(folder)
        counts = Counter(r.get("verdict") for r in results)
        done = (folder / "scan_report.json").exists()
        lines += [f"## {folder.name}", "", f"Relatório final: {'sim' if done else 'não (rodada incompleta)'}. "
                  f"Hipóteses verificadas: {len(results)}. Vereditos: {dict(counts)}", ""]
        for r in results:
            if r.get("verdict") in LISTED:
                h = r["hypothesis"]
                lines += [f"- **{r['verdict']}** `{h['function']}` em `{h['file'].split('/alvos')[-1]}`: "
                          f"`{h['suspect_expression'][:90]}`", f"  - gatilho: {h['trigger_condition'][:240]}"]
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(summarize(args.folders), encoding="utf-8")
    print(f"escrito: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
