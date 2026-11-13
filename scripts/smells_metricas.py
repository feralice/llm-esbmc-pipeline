"""Precision and recall of PySmell's own heuristics against the hand labels, with no LLM call.

    python scripts/smells_metricas.py --out artifacts/smells/pysmell-so-metricas.md

Baseline for the smell track: the LLM filter must beat it to justify its calls. Positives per smell are
printed beside each score because some smells have only a handful (LongMethod has 2).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from smell_filter_pysmell import DATASET, pysmell_candidates

from research_pipeline.smells.filter import score


NOTE = ("\nAviso: a revocação perto de 100% pode ser circular. Confira se os itens do conjunto foram sorteados "
        "entre os sinalizados pela própria ferramenta antes de citar esse número.\n")


def tool_only(rows: list[dict]) -> dict:
    candidates, labels = pysmell_candidates(rows)
    return score(candidates, labels, {})


def _percent(value: float | None) -> str:
    return "n/d" if value is None else f"{100 * value:.1f}%"


def table(result: dict, rows: list[dict]) -> str:
    positives = Counter(row["smell"] for row in rows if row["label"] == 1)
    lines = ["| Smell | Positivos | Precisão | Revocação | Sinalizados | Falsos positivos |", "|---|---:|---:|---:|---:|---:|"]
    for smell, block in sorted(result["per_smell"].items()):
        tool = block["tool"]
        lines.append(f"| {smell} | {positives[smell]} | {_percent(tool['precision'])} | {_percent(tool['recall'])} | "
                     f"{tool['tp'] + tool['fp']} | {tool['fp']} |")
    total = result["tool"]
    lines.append(f"| Todos | {sum(positives.values())} | {_percent(total['precision'])} | {_percent(total['recall'])} | "
                 f"{total['tp'] + total['fp']} | {total['fp']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    text = "# Heurísticas do PySmell contra os rótulos manuais (sem LLM)\n\n" + table(tool_only(rows), rows) + NOTE
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
