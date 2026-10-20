"""Where each ground-truth bug stopped in a finished run: one stage per bug, not per hypothesis.

Only hypotheses at the bug line (v2_evaluator.at_bug_line) count past detection; among them the
furthest verdict decides. An orchestrator confirmation of such a hypothesis counts as confirmed.

  python scripts/v2_funnel.py artifacts/v2/final-2026-10-15-codex --out artifacts/v2/funil-2026-10-16
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402

STAGES = ("mudanca_de_comportamento", "fora_da_rodada", "sem_hipotese", "hipotese_fora_da_linha", "cortado_pelo_limite_do_llm",
          "harness_nao_montado", "esbmc_recusou", "so_llm", "esbmc_rodou_sem_confirmar", "confirmado")
_BY_VERDICT = {
    "PIPELINE_ERROR": "cortado_pelo_limite_do_llm",
    "GROUNDING_FAILED": "harness_nao_montado", "NO_SOURCE": "harness_nao_montado",
    "SPEC_FAILED": "harness_nao_montado",
    "UNSUPPORTED": "esbmc_recusou", "MISSING_DEPENDENCY": "esbmc_recusou", "ESBMC_ERROR": "esbmc_recusou",
    "ESBMC_TIMEOUT": "esbmc_recusou", "LLM_ONLY": "so_llm",
    "NOT_CONFIRMED": "esbmc_rodou_sem_confirmar", "UNVALIDATED": "esbmc_rodou_sem_confirmar",
    "OTHER_FAILURE": "esbmc_rodou_sem_confirmar", "ESBMC_MISSED": "esbmc_rodou_sem_confirmar",
    "VALUE_VIOLATION": "esbmc_rodou_sem_confirmar", "PROPERTY_REJECTED": "esbmc_rodou_sem_confirmar",
    "CONFIRMED": "confirmado", "VALUE_CONFIRMED": "confirmado",
}


def stage(verdicts: list[str]) -> str:
    return max((_BY_VERDICT[v] for v in verdicts), key=STAGES.index)


def bug_stage(*, in_run: bool, verdicts: list[str], at_line: list[str], behaviour_change: bool = False) -> str:
    if behaviour_change:
        return "mudanca_de_comportamento"
    if not in_run:
        return "fora_da_rodada"
    if not verdicts:
        return "sem_hipotese"
    if not at_line:
        return "hipotese_fora_da_linha"
    return stage(at_line)


def funnel(run: Path, ground_truth: Path) -> list[dict]:
    items = json.loads(ground_truth.read_text(encoding="utf-8"))["items"]
    in_run = {Path(f).stem for f in json.loads((run / "v2_report.json").read_text(encoding="utf-8"))["config"]["input_files"]}
    results = json.loads((run / "v2_verify_report.json").read_text(encoding="utf-8"))["results"]
    orchestrated = run / "orq_free" / "orchestrated.json"
    orq_confirmed = ({row["hypothesis_id"] for row in json.loads(orchestrated.read_text(encoding="utf-8"))["rows"]
                      if row.get("final") == "CONFIRMED"} if orchestrated.exists() else set())
    by_bug: dict[str, list[dict]] = {}
    for result in results:
        by_bug.setdefault(Path(result["hypothesis"]["file"]).stem, []).append(result)
    rows = []
    for item in items:
        mine = by_bug.get(item["id"], [])
        at_line = [r for r in mine if at_bug_line(r["hypothesis"], item)]
        verdicts_at_line = ["CONFIRMED" if r["hypothesis"]["hypothesis_id"] in orq_confirmed else r["verdict"]
                            for r in at_line]
        rows.append({"id": item["id"], "failure_kind": item.get("failure_kind", ""),
                     "stage": bug_stage(in_run=item["id"] in in_run, verdicts=[r["verdict"] for r in mine],
                                        at_line=verdicts_at_line,
                                        behaviour_change="behaviour_change" in item),
                     "hypotheses": len(mine), "at_line": len(at_line),
                     "verdicts_at_line": dict(Counter(verdicts_at_line))})
    return rows


def render(rows: list[dict]) -> str:
    counts = Counter(r["stage"] for r in rows)
    lines = ["| Etapa onde parou | Bugs |", "|---|---|"]
    lines += [f"| {s} | {counts.get(s, 0)} |" for s in STAGES]
    lines.append(f"| **total** | **{len(rows)}** |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="finished run folder (v2_report.json, v2_verify_report.json, orq_free/)")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = funnel(Path(args.run), Path(args.ground_truth))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "funil.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "funil.md").write_text(render(rows), encoding="utf-8")
    print(render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
