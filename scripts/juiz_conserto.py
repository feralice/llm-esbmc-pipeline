"""O conserto dos mantenedores como juiz, sem LLM: a entrada que quebrou a versão com bug quebra a corrigida?

Para cada hipótese reproduzida com entrada guardada, roda de novo o programa de replay trocando a função pela
versão corrigida (o mesmo mecanismo do controle de valor, verify/value_oracle.check_fixed).
  fixed_ok     a versão corrigida não levanta a exceção com a mesma entrada
  fixed_breaks a versão corrigida também levanta: a suspeita não é o que o conserto tratou
  unavailable  não deu para montar o controle (o motivo vai na coluna)
Uso: python scripts/juiz_conserto.py RELATORIO.json [--dataset dataset/disciplina_pgene601]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from research_pipeline.verify.render import Program  # noqa: E402
from research_pipeline.verify.value_oracle import check_fixed  # noqa: E402

_STATUS = {"not_reproduced": "fixed_ok", "reproduced": "fixed_breaks", "property_violated": "fixed_breaks"}


def _spans(source: str, name: str) -> tuple[tuple[int, int], ...]:
    return tuple((n.lineno, n.end_lineno) for n in ast.walk(ast.parse(source))
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def judge(result: dict, dataset: Path) -> tuple[str, str]:
    replay, h = result.get("replay") or {}, result["hypothesis"]
    case = Path(h["file"]).stem
    fixed_file, buggy_file = dataset / "arquivo_corrigido" / f"{case}.py", dataset / "arquivo_com_bug" / f"{case}.py"
    if not fixed_file.exists() or not buggy_file.exists():
        return "unavailable", "sem versão corrigida ou com bug no dataset"
    program_path = Path(result["program_path"])
    replay_path = program_path.with_name(program_path.stem + "_replay.py")
    source = program_path.read_text(encoding="utf-8")
    replay_source = replay_path.read_text(encoding="utf-8") if replay_path.exists() else source
    name = h["function"].split(".")[-1]
    driver = next((i for i, line in enumerate(source.splitlines(), 1) if line.startswith("def _esbmc_main")), 0)
    program = Program(source, driver, _spans(source, name), (), tuple(replay.get("target_range") or (0, 0)),
                      replay_source=replay_source, replay_target_spans=_spans(replay_source, name))
    verdict = check_fixed(program, h["function"], name, fixed_file.read_text(encoding="utf-8"),
                          replay.get("inputs"), original_source=buggy_file.read_text(encoding="utf-8"),
                          draws=replay.get("draws"))
    return _STATUS.get(verdict.status, "unavailable"), verdict.reason or verdict.exception_type or verdict.status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--dataset", type=Path, default=Path("dataset/disciplina_pgene601"))
    args = parser.parse_args()
    results = json.loads(args.report.read_text(encoding="utf-8"))["results"]
    rows = []
    for result in results:
        replay = result.get("replay") or {}
        if replay.get("status") != "reproduced" or not replay.get("inputs") or not result.get("program_path"):
            continue
        try:
            status, detail = judge(result, args.dataset)
        except Exception as exc:  # noqa: BLE001 - one case must not stop the table
            status, detail = "unavailable", f"{type(exc).__name__}: {exc}"
        rows.append((Path(result["hypothesis"]["file"]).stem, result["hypothesis"]["function"], result["verdict"],
                     replay.get("exception_type", ""), status, detail[:90]))
    print("caso | função | veredito | exceção no bug | juiz | detalhe")
    for row in rows:
        print(" | ".join(row))
    from collections import Counter
    print(Counter(r[4] for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
