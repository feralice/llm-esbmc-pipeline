"""Compare verify runs bug by bug: exact McNemar, paired bootstrap and a cost table.

    python scripts/pareado.py A_DIR B_DIR [C_DIR ...] --out comparacao.md [--metric expression_equivalent]

Each DIR holds v2_verify_report.json. The first DIR is the reference; every other is paired with it. A bug counts as
confirmed when some CONFIRMED hypothesis points at it by the chosen metric (default: equivalent expression).
"""

from __future__ import annotations

import argparse
import json
import random
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = ("detection", "synthesis")


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact p-value: binomial(n, 1/2) over the bugs where the runs disagree."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2**n
    return min(1.0, 2 * tail)


def discordant(a: dict[str, bool], b: dict[str, bool]) -> tuple[int, int]:
    shared = a.keys() & b.keys()
    return sum(a[k] and not b[k] for k in shared), sum(b[k] and not a[k] for k in shared)


def bootstrap_difference(a: dict[str, bool], b: dict[str, bool], *, seed: int = 0, rounds: int = 10000) -> tuple[int, int]:
    """95% interval of (bugs confirmed in a) minus (bugs confirmed in b), resampling bugs with replacement."""
    ids = sorted(a.keys() & b.keys())
    rng = random.Random(seed)
    diffs = sorted(
        sum(a[k] - b[k] for k in (rng.choice(ids) for _ in ids)) for _ in range(rounds)
    )
    return diffs[int(0.025 * rounds)], diffs[int(0.975 * rounds) - 1]


def confirmed_bugs(report: dict, metric: str = "expression_equivalent") -> dict[str, bool]:
    """Per labelled bug: did some CONFIRMED hypothesis match it? Reuses the evaluator, one bug at a time."""
    from research_pipeline.v2_evaluator import _bug_detection_metrics
    from research_pipeline.verify.outcome import CONFIRMED
    from research_pipeline.verify.report import _expected_items

    config = report["config"]
    ground_truth = ROOT / "dataset/disciplina_pgene601/ground_truths.json"
    items, base = _expected_items(ground_truth, config["input_files"])
    found = [{"file": r["hypothesis"]["file"], "function": r["hypothesis"]["function"],
              "expression": r["hypothesis"]["suspect_expression"]}
             for r in report["results"] if r["verdict"] == CONFIRMED]
    result = {}
    for item in items:
        if item.get("categories"):
            result[str(item["id"])] = _bug_detection_metrics([item], found, base)[metric]["tp"] == 1
    return result


def cost_row(report: dict) -> dict:
    telemetry = report.get("telemetry") or {}
    stages = [telemetry.get(s) or {} for s in STAGES]

    def total(key: str) -> float:
        return sum(s.get(key) or 0 for s in stages)

    measured = all(s.get("calls_with_cache_data") for s in stages if s.get("calls"))
    return {"calls": int(total("calls")), "prompt_tokens": int(total("prompt_tokens")) if measured else None,
            "tokens": int(total("tokens")), "cost_usd": round(total("cost_usd"), 2) if measured else None,
            "seconds": round(total("seconds"))}


def acceptance(report: dict) -> tuple[int, int]:
    """Hypotheses that ended with a checked verdict, out of all hypotheses."""
    from research_pipeline.verify.outcome import CHECKED

    results = report["results"]
    return sum(r["verdict"] in CHECKED for r in results), len(results)


def _show(value: float | None) -> float | str:
    return "n/d" if value is None else value


def build(runs: list[tuple[str, dict]], metric: str) -> str:
    bugs = {name: confirmed_bugs(report, metric) for name, report in runs}
    reference_name = runs[0][0]
    lines = [f"# Comparação pareada ({metric})", "",
             "| Configuração | Bugs confirmados | Hipóteses | Com veredito | Chamadas | Tokens de entrada | Custo equiv. (US$) | Tempo (s) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, report in runs:
        row, (checked, total) = cost_row(report), acceptance(report)
        lines.append(f"| {name} | {sum(bugs[name].values())} de {len(bugs[name])} | {total} | {checked} | "
                     f"{row['calls']} | {_show(row['prompt_tokens'])} | {_show(row['cost_usd'])} | {row['seconds']} |")
    lines += ["", f"Referência: {reference_name}. A diferença é referência menos a configuração.", "",
              "| Configuração | Só na referência | Só na configuração | Diferença líquida | IC 95% (bootstrap) | p (McNemar exato) |",
              "|---|---:|---:|---:|---:|---:|"]
    for name, _ in runs[1:]:
        only_ref, only_other = discordant(bugs[reference_name], bugs[name])
        low, high = bootstrap_difference(bugs[reference_name], bugs[name])
        lines.append(f"| {name} | {only_ref} | {only_other} | {only_ref - only_other} | [{low}, {high}] | "
                     f"{mcnemar_exact(only_ref, only_other):.4f} |")
    lines += ["", "p abaixo de 0,05 só aparece com 6 ou mais bugs discordantes na mesma direção. "
              "Diferença menor fica como não distinguível."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metric", default="expression_equivalent")
    args = parser.parse_args()
    runs = [(d.name, json.loads((d / "v2_verify_report.json").read_text(encoding="utf-8"))) for d in args.dirs]
    args.out.write_text(build(runs, args.metric), encoding="utf-8")
    print(f"escrito: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
