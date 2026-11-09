"""Compare two verify reports (same hypotheses, different pipeline or ESBMC) and write a Markdown summary.

    python scripts/compare_runs.py OLD_DIR NEW_DIR --out NEW_DIR/resumo.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

Key = tuple[str, str, str]


def _key(result: dict) -> Key:
    h = result["hypothesis"]
    return h["file"], h["function"], h["suspect_expression"]


def counts(report: dict) -> dict[str, int]:
    return dict(Counter(r["verdict"] for r in report["results"]))


def total_seconds(report: dict) -> float:
    return sum(r.get("seconds") or 0.0 for r in report["results"])


def changes(old: dict, new: dict) -> tuple[list[tuple[Key, str, str]], list[Key], list[Key]]:
    before = {_key(r): r["verdict"] for r in old["results"]}
    after = {_key(r): r["verdict"] for r in new["results"]}
    changed = [(k, before[k], after[k]) for k in before if k in after and before[k] != after[k]]
    return changed, [k for k in before if k not in after], [k for k in after if k not in before]


def _levels(report: dict) -> str:
    """Bugs confirmed by the bug's expression (the strict metric) and by any line of its function, plus the bugs
    whose function failed under ESBMC and CPython at another line (OTHER_FAILURE), which no level confirms."""
    evaluation = report.get("evaluation") or {}
    confirmed = evaluation.get("confirmed_by_location", {})
    if not confirmed:
        return "sem gabarito"
    total = confirmed["expression_equivalent"]["tp"] + confirmed["expression_equivalent"]["fn"]
    strict = confirmed["expression_equivalent"]["tp"]
    function = confirmed["location"]["tp"]
    other = evaluation.get("same_function_other_line", {}).get("bugs_not_confirmed_at_line", 0)
    return (f"{strict} pela expressão e {function} pela função, de {total}; "
            f"{other} com falha em outra linha da função e sem confirmação na linha do bug")


def summarize(old: dict, new: dict) -> str:
    old_counts, new_counts = counts(old), counts(new)
    lines = ["# Comparação das rodadas", "",
             f"Hipóteses: {len(old['results'])} (antes) e {len(new['results'])} (agora).",
             f"Bugs confirmados pelo ESBMC: {_levels(old)} (antes), {_levels(new)} (agora).",
             f"Tempo somado por hipótese: {total_seconds(old) / 3600:.1f} h (antes), {total_seconds(new) / 3600:.1f} h (agora).",
             "",
             "| Veredito | Antes | Agora |", "|---|---:|---:|"]
    for verdict in sorted(set(old_counts) | set(new_counts), key=lambda v: -(new_counts.get(v, 0))):
        lines.append(f"| {verdict} | {old_counts.get(verdict, 0)} | {new_counts.get(verdict, 0)} |")
    changed, only_old, only_new = changes(old, new)
    lines += ["", f"## Hipóteses com veredito diferente ({len(changed)})", ""]
    lines += [f"- `{k[1]}` `{k[2][:70]}`: {a} para {b}" for k, a, b in sorted(changed, key=lambda c: (c[1], c[2]))]
    lines += ["", f"Só na rodada antiga: {len(only_old)}. Só na nova: {len(only_new)}."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    old, new = (json.loads((d / "v2_verify_report.json").read_text(encoding="utf-8")) for d in (args.old, args.new))
    args.out.write_text(summarize(old, new), encoding="utf-8")
    print(f"escrito: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
