"""Mine an agent run for repair candidates: a round ESBMC refused followed by one that reached a verdict.

Since 05/11 the hybrid and scan modes of main.py add these repairs to the notebook
(src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md) by themselves, unless --no-auto-lessons; this
script stays for offline review of other runs (older ones, scripts/v2_agent_arm.py). It writes candidatos.md next to agent_results.json for the researcher to review; a rule she approves enters
through scripts/add_repair.py.

    python scripts/v2_repair_candidates.py artifacts/v2/<agent-run>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.lessons import round_repairs  # noqa: E402


def _load_results(run_dir: Path) -> dict[str, dict]:
    results = Path(run_dir) / "agent_results.json"
    if not results.exists():
        return {}
    return {entry["hypothesis"]["hypothesis_id"]: entry
            for entry in json.loads(results.read_text(encoding="utf-8"))}


def repair_candidates(case_dir: Path, results: dict[str, dict] | None = None) -> list[dict]:
    """Only finished cases count: no entry in agent_results.json (or no file) means no candidates."""
    case_dir = Path(case_dir)
    if results is None:
        results = _load_results(case_dir.parents[1])
    return round_repairs(case_dir, results.get(case_dir.name))


def write_candidates(run_dir: Path, out: Path) -> int:
    results = _load_results(run_dir)
    candidates = [c for case in sorted((Path(run_dir) / "cases").glob("*")) if case.is_dir()
                  for c in repair_candidates(case, results)]
    lines = ["# Candidatos ao caderno de reparos", "",
             "Pares de rodadas em que o ESBMC recusou e a rodada seguinte chegou a um veredito. "
             "Nada daqui entra no caderno sem aprovação: a regra escolhida entra por scripts/add_repair.py "
             "(a versão é o hash do arquivo, registrado a cada rodada).", ""]
    for c in candidates:
        lines += [f"## {c['caso']}, rodada {c['rodada']}", "", f"Erro: `{c['erro']}`", "",
                  "```diff", c["diff"].rstrip("\n"), "```", ""]
    if not candidates:
        lines.append("Nenhum candidato nesta rodada.")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                     epilog="Since 05/11 main.py's hybrid and scan runs add these lessons to the "
                                            "notebook automatically (--no-auto-lessons keeps it fixed); this "
                                            "script reviews other runs offline.")
    parser.add_argument("run_dir", help="agent-arm output folder (holds cases/ and agent_results.json)")
    args = parser.parse_args()
    out = Path(args.run_dir) / "candidatos.md"
    print(f"{write_candidates(Path(args.run_dir), out)} candidatos em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
