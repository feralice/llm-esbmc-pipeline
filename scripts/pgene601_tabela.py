"""Comparison table for the PGENE601 report: mypy, the PR tests and the pipeline runs on the same 47 bugs.

    python scripts/pgene601_tabela.py --run "06/11 (antes de olhar os 47)=artifacts/pgene601/congelado-c-2026-11-06" \
        --run "08/11 (depois da análise de erros)=artifacts/pgene601/rodada-2026-11-08" --out tabela.md

Counting rule of each row is in the table. Runs after 06/11 are not out-of-sample: the 47 guided their fixes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MYPY = ROOT / "artifacts/pgene601/mypy-2026-11-03/mypy_cps.json"
PYTEST = ROOT / "artifacts/pgene601/pytest-2026-11-03/pytest_results.json"


def mypy_hits(rows: list[dict]) -> tuple[int, int, int]:
    return sum(bool(r["default"]) for r in rows), sum(bool(r["strict"]) for r in rows), len(rows)


def pipeline_row(label: str, run: Path) -> str:
    evaluation = json.loads((run / "v2_verify_report.json").read_text())["evaluation"]
    detected = evaluation["detection_by_location"]["expression_equivalent"]["tp"]
    confirmed = evaluation["confirmed_by_location"]
    return (f"| Pipeline, {label} | {confirmed['expression_equivalent']['tp']} | {confirmed['location']['tp']} | "
            f"{detected} |")


def build(runs: list[tuple[str, Path]]) -> str:
    rows = json.loads(MYPY.read_text())
    default, strict, total = mypy_hits(rows)
    pytest = json.loads(PYTEST.read_text())
    lines = [
        f"# Comparação nos {total} bugs da disciplina", "",
        "## Métodos que não são o pipeline", "",
        "| Método | Bugs apontados | Regra de contagem |", "|---|---:|---|",
        f"| mypy, opções padrão | {default} | erro do mypy na linha do bug ou nas linhas `crash_expressions` |",
        f"| mypy, `--check-untyped-defs` | {strict} | mesma regra; só 3 trazem a mensagem certa para o bug |",
        (f"| testes do PR (pytest) | {pytest['bug_specific_differential_cases']} | o teste falha no código com bug e "
         f"passa no corrigido; {pytest['cases_without_python_pr_test_files']} bugs não têm teste Python no PR |"),
        "", "## Pipeline (LLM + ESBMC)", "",
        ("| Rodada | Confirmados pelo ESBMC (expressão equivalente) | Confirmados pela função | "
         "Hipótese certa do detector |"),
        "|---|---:|---:|---:|", *(pipeline_row(label, run) for label, run in runs), "",
        ("Leitura: o detector entrega a hipótese certa em muito mais bugs do que o ESBMC confirma. A diferença "
         "mostra onde o pipeline perde (limites do frontend do ESBMC e montagem do harness), não a capacidade de "
         "achar o bug."),
        "",
        ("Aviso de método: a rodada de 06/11 foi feita com o pipeline congelado antes de olhar os 47 e vale como teste "
         "fora da amostra. As rodadas depois dela usam consertos escolhidos a partir de erros nesses mesmos 47, "
         "então medem o pipeline depois de uma análise de erros e não devem ser chamadas de fora da amostra."),
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", default=[], help="LABEL=PASTA")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    runs = [(item.split("=", 1)[0], Path(item.split("=", 1)[1])) for item in args.run]
    Path(args.out).write_text(build(runs))
    print(f"escrito: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
