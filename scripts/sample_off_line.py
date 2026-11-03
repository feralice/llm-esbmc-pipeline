"""Sample detection hypotheses that miss the labelled bug line, for hand labelling.

The question behind it (PLANO_2026-10-19, "Depois"): when A5 points away from the bug's line, is it wrong,
or is the line metric too strict (same bug elsewhere, another real bug)? Writes a CSV to label and a
Markdown file with each hypothesis next to the code and the labelled bug.

    python scripts/sample_off_line.py artifacts/v2/det-2026-10-31-en-r1-A1,A2 artifacts/v2/det-2026-10-31-en-r2-A1,A2 \
        --out docs/experimentos/rotulo_fora_da_linha_2026-11-02
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import random
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line
from research_pipeline.verify.astutil import expression_nodes, locate

sys.path.insert(0, str(ROOT / "scripts"))
from v2_self_consistency import undo_prompt_rename

LABELS = ("mesmo_bug_outra_linha", "outro_bug_real", "falso_positivo", "nao_sei")
COLUMNS = ("caso", "bug", "funcao", "expressao_llm", "explicacao_llm", "funcao_gabarito", "expressao_gabarito",
           "rodadas", "rotulo", "observacao")


def off_line(runs: list[Path], items: dict, sample: set[str]) -> list[dict]:
    found: dict[tuple, dict] = {}
    for run in runs:
        units = json.loads((run / "v2_checkpoint.json").read_text(encoding="utf-8"))["detection_units"]
        for unit in units.values():
            for candidate in unit.get("candidates", []):
                bug = Path(candidate["file"]).stem
                if bug not in sample:
                    continue
                expression = undo_prompt_rename(candidate["expression"], candidate["function"])
                hypothesis = {"function": candidate["function"], "suspect_expression": expression}
                if at_bug_line(hypothesis, items[bug]):
                    continue
                key = (bug, candidate["function"], " ".join(expression.split()))
                row = found.setdefault(key, {"bug": bug, "file": candidate["file"], "function": candidate["function"],
                                             "expression": expression, "note": candidate.get("note", ""),
                                             "runs": set()})
                row["runs"].add(run.name)
    return sorted(found.values(), key=lambda r: (r["bug"], r["function"], r["expression"]))


def _marked_source(path: Path, function: str, expressions: dict[str, str]) -> str:
    """The function's source with ``>> LABEL`` at the end of the lines holding each expression."""
    source = path.read_text(encoding="utf-8", errors="replace")
    target = locate(ast.parse(source), function)
    if target is None:
        return "(função não encontrada no arquivo)"
    lines = source.splitlines()
    marks: dict[int, list[str]] = {}
    for label, expression in expressions.items():
        for node in expression_nodes(target, expression) if expression else []:
            marks.setdefault(node.lineno, []).append(label)
    first = min([target.lineno, *(d.lineno for d in target.decorator_list)])
    return "\n".join(line + (f"    # >> {', '.join(marks[n])}" if n in marks else "")
                     for n, line in enumerate(lines[first - 1:target.end_lineno], first))


def _flat(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample", default="dataset/bugs_reais/amostra_deteccao.json")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    args = parser.parse_args()
    items = {i["id"]: i for i in json.loads((ROOT / args.ground_truth).read_text(encoding="utf-8"))["items"]}
    sample = {Path(f).stem for f in json.loads((ROOT / args.sample).read_text(encoding="utf-8"))["files"]}
    sample = {b for b in sample if "behaviour_change" not in items[b]}
    pool = off_line(args.runs, items, sample)
    chosen = sorted(random.Random(args.seed).sample(pool, min(args.n, len(pool))), key=lambda r: r["bug"])
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "rotulos.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, COLUMNS)
        writer.writeheader()
        for number, row in enumerate(chosen, 1):
            item = items[row["bug"]]
            writer.writerow({"caso": number, "bug": row["bug"], "funcao": row["function"],
                             "expressao_llm": row["expression"], "explicacao_llm": row["note"],
                             "funcao_gabarito": item["function"], "expressao_gabarito": item.get("expression", ""),
                             "rodadas": len(row["runs"]), "rotulo": "", "observacao": ""})
    parts = [f"# {len(chosen)} hipóteses da A5 fora da linha do bug\n",
             (f"Sorteio de {len(chosen)} entre {len(pool)} hipóteses distintas fora da linha, semente {args.seed}, "
              f"rodadas: {', '.join(r.name for r in args.runs)}.\n"),
             "Rótulos (coluna `rotulo` do `rotulos.csv`): " + ", ".join(f"`{label}`" for label in LABELS) + ".\n"]
    for number, row in enumerate(chosen, 1):
        item = items[row["bug"]]
        same_function = row["function"] in {f.strip() for f in item["function"].split("/")}
        code = _marked_source(ROOT / row["file"], row["function"],
                              {"LLM": row["expression"],
                               **({"GABARITO": item.get("expression", "")} if same_function else {})})
        parts.append(f"## Caso {number}: {row['bug']}\n\n"
                     f"- **LLM:** `{row['function']}`: `{_flat(row['expression'])}`\n"
                     f"- **Explicação da LLM:** {row['note']}\n"
                     f"- **Gabarito:** `{item['function']}`: `{_flat(item.get('expression', ''))}`\n"
                     f"- **Rodadas que propuseram:** {len(row['runs'])} de {len(args.runs)}\n\n"
                     f"```python\n{code}\n```\n")
    (args.out / "casos.md").write_text("\n".join(parts), encoding="utf-8")
    print(f"{len(pool)} hipóteses fora da linha; {len(chosen)} sorteadas em {args.out}")
    return 0


if __name__ == "__main__":
    warnings.simplefilter("ignore", SyntaxWarning)  # escape sequences in the dataset's own sources
    raise SystemExit(main())
