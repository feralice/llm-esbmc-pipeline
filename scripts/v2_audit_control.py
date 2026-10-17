"""Audit of a run's confirmations against the fixed version, without any LLM call.

Each CONFIRMED hypothesis is verified again with the specs its LLM gave (current harness and ESBMC);
the input the replay found is then given to the fixed version of the function. A confirmation holds
when the fixed version runs clean with it; an exception there says the input breaks the corrected code
too, so it is not evidence of the dataset's bug.

  python scripts/v2_audit_control.py artifacts/v2/final-2026-10-15-codex/v2_verify_report.json \
      --out artifacts/v2/auditoria-2026-10-16
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from v2_replay_specs import RecordedSpecs  # noqa: E402

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402
from research_pipeline.verification.esbmc_runner import DEFAULT_ESBMC  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402
from research_pipeline.verify.loop import precheck, verification_source, verify_hypothesis  # noqa: E402
from research_pipeline.verify.render import render_program  # noqa: E402
from research_pipeline.verify.spec import parse_spec, shape_unpacked  # noqa: E402
from research_pipeline.verify.value_oracle import check_fixed  # noqa: E402

HOLDS, CHANGED, BREAKS_FIXED = "vale", "corrigida_muda_o_comportamento", "corrigida_quebra_igual"
NO_CONTROL, LOST = "sem_controle", "nao_confirma_mais"


def control_outcome(verdict: str, control_status: str | None, exception: str, control_exception: str | None) -> str:
    """Only the same exception in the fixed version takes a confirmation away. Another one is a changed
    behaviour: a fix may raise a clearer error for the same input (dz_real_03), or the harness may lack
    a name only the fix uses."""
    if verdict != "CONFIRMED":
        return LOST
    if control_status == "not_reproduced":
        return HOLDS
    if control_status in {"reproduced", "other_failure"}:
        return BREAKS_FIXED if control_exception == exception else CHANGED
    return NO_CONTROL


def audit(item: dict, gt: dict, *, esbmc: list[str], timeout: int, sources: Path, fixed: Path, work: Path) -> dict:
    raw = item["hypothesis"]
    h = BugHypothesis(**{k: v for k, v in raw.items() if k != "hypothesis_id"})
    h = BugHypothesis(**{**h.__dict__, "file": str(ROOT / h.file)})
    source = verification_source(h, sources).read_text(encoding="utf-8", errors="replace")
    specs = [a["spec"] for a in item["attempts"] if "spec" in a]
    result = verify_hypothesis(h, llm=RecordedSpecs(specs), source=source, esbmc_command=esbmc, bound=5,
                               timeout_seconds=timeout, work_dir=work / raw["hypothesis_id"])
    row = {"id": Path(raw["file"]).stem, "hypothesis_id": raw["hypothesis_id"], "function": raw["function"],
           "at_line": at_bug_line(raw, gt), "verdict_before": item["verdict"], "verdict_now": result.verdict,
           "exception": (result.replay or {}).get("exception_type"), "inputs": (result.replay or {}).get("inputs")}
    control = None
    fixed_file = fixed / Path(raw["file"]).name
    if result.verdict == "CONFIRMED" and fixed_file.exists():
        grounded, _, _ = precheck(h, source, esbmc)
        spec = shape_unpacked(parse_spec(next(a["spec"] for a in reversed(result.attempts) if "spec" in a)), grounded)
        program = render_program(grounded, spec)
        control = check_fixed(program, h.function, grounded.method_name, fixed_file.read_text(encoding="utf-8"),
                              row["inputs"])
        row["control"] = {"status": control.status, "exception": control.exception_type, "reason": control.reason}
    row["outcome"] = control_outcome(result.verdict, control.status if control else None, row["exception"],
                                     control.exception_type if control else None)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--esbmc", default=DEFAULT_ESBMC)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--fixed-sources", default="dataset/bugs_reais/arquivo_corrigido")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    gt = {i["id"]: i for i in json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))["items"]}
    results = json.loads(Path(args.report).read_text(encoding="utf-8"))["results"]
    rows = []
    for item in [r for r in results if r["verdict"] == "CONFIRMED"]:
        row = audit(item, gt[Path(item["hypothesis"]["file"]).stem], esbmc=shlex.split(args.esbmc),
                    timeout=args.timeout, sources=ROOT / args.sources, fixed=ROOT / args.fixed_sources,
                    work=out / "programs")
        rows.append(row)
        print(f"{row['id']:16s} linha={row['at_line']!s:5s} {row['verdict_now']:14s} {row['outcome']}", flush=True)
    (out / "auditoria.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
