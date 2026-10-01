"""Combine an engine report with agent results: which level decided each hypothesis, and why the
rest stayed with the LLM alone. Prints the table and writes the rows.

  python3 scripts/v2_levels.py --engine <v2_verify_report.json ...> [--agent <agent_results.json ...>] --out levels.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.levels import LIMIT_GROUPS, consolidate, level_summary  # noqa: E402

_LIMIT_LABELS = {
    "harness_context": "contexto da função (nomes, stubs, tipos de entrada)",
    "esbmc_language": "recurso de Python que o ESBMC não tem, no corpo da função",
    "esbmc_crash": "falha interna do ESBMC",
    "esbmc_timeout": "tempo esgotado",
    "llm_spec": "a LLM não deu tipos válidos",
    "locate_function": "função ou arquivo não encontrado",
    "network": "falha de rede",
    "pipeline_error": "falha do próprio pipeline",
    "other": "motivo não classificado",
    "agent_rewrote_function": "o agente alterou a função",
}


def _load(paths: list[str], key: str) -> list[dict]:
    items: list[dict] = []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        items += data.get(key, []) if isinstance(data, dict) else data
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", nargs="+", required=True, help="reports with a 'results' list")
    parser.add_argument("--agent", nargs="*", default=[], help="agent_results.json files")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = consolidate(_load(args.engine, "results"), _load(args.agent, "agent_results"))
    summary = level_summary(rows)
    n = summary["hypotheses"]
    print(f"{n} hipóteses")
    for level, label in (("esbmc_engine", "ESBMC pelo harness determinístico"), ("esbmc_agent", "ESBMC pelo agente"),
                         ("esbmc_agent_simplified", "ESBMC na função simplificada, confirmado no código original"),
                         ("llm_only", "só a LLM")):
        count = summary["by_level"].get(level, 0)
        confirmed = summary["confirmed_by_level"].get(level, 0)
        extra = f", {confirmed} confirmado(s)" if level in ("esbmc_engine", "esbmc_agent") else ""
        print(f"  {count:4d} ({100 * count / max(n, 1):4.1f}%)  {label}{extra}")
    print("Só a LLM, por motivo:")
    for group in LIMIT_GROUPS:
        if summary["llm_only_by_limit"][group]:
            print(f"  {summary['llm_only_by_limit'][group]:4d}  {_LIMIT_LABELS[group]}")
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
