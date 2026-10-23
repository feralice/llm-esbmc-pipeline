"""Mine an agent run for repair candidates: a round ESBMC refused followed by one that reached a verdict.

Nothing enters the notebook (src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md) by itself: this
writes candidatos.md next to agent_results.json for the researcher to review and approve by hand.

    python scripts/v2_repair_candidates.py artifacts/v2/<agent-run>
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.rounds import read_rounds  # noqa: E402


def _preservation(case_dir: Path) -> str:
    results = case_dir.parents[1] / "agent_results.json"
    if not results.exists():
        return ""
    for entry in json.loads(results.read_text(encoding="utf-8")):
        if entry["hypothesis"]["hypothesis_id"] == case_dir.name:
            return (entry.get("differential") or {}).get("preservation", "")
    return ""


def _first_error(output: str) -> str:
    lines = output.splitlines()
    return next((line for line in lines if line.startswith("ERROR:")), lines[0] if lines else "")


def repair_candidates(case_dir: Path) -> list[dict]:
    case_dir = Path(case_dir)
    if _preservation(case_dir) == "alterada":
        return []
    rounds = read_rounds(case_dir)
    return [{"caso": case_dir.name, "rodada": first.index, "erro": _first_error(first.output),
             "diff": "".join(difflib.unified_diff(first.source.splitlines(keepends=True),
                                                  second.source.splitlines(keepends=True),
                                                  f"rodada {first.index:03d}", f"rodada {second.index:03d}"))}
            for first, second in zip(rounds, rounds[1:])
            if first.kind == "refused" and second.kind == "verdict"]


def write_candidates(run_dir: Path, out: Path) -> int:
    candidates = [c for case in sorted((Path(run_dir) / "cases").glob("*")) if case.is_dir()
                  for c in repair_candidates(case)]
    lines = ["# Candidatos ao caderno de reparos", "",
             "Pares de rodadas em que o ESBMC recusou e a rodada seguinte chegou a um veredito. "
             "Nada daqui entra no caderno sem aprovação: copie a regra escolhida para o SKILL.md "
             "de reparos-aprendidos e incremente a versão.", ""]
    for c in candidates:
        lines += [f"## {c['caso']}, rodada {c['rodada']}", "", f"Erro: `{c['erro']}`", "",
                  "```diff", c["diff"].rstrip("\n"), "```", ""]
    if not candidates:
        lines.append("Nenhum candidato nesta rodada.")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run_dir", help="agent-arm output folder (holds cases/ and agent_results.json)")
    args = parser.parse_args()
    out = Path(args.run_dir) / "candidatos.md"
    print(f"{write_candidates(Path(args.run_dir), out)} candidatos em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
