"""Does a failure found at another line of a bug's function disappear in the fixed version?

For each CONFIRMED or OTHER_FAILURE hypothesis whose function holds a labelled bug, the same hypothesis runs on the
fixed file, with the spec the buggy run ended on (no LLM call). Only NOT_CONFIRMED on the fixed file shows
the patch removes the failure; the same verdict on both files suggests a failure the patch left alone, unless the
harness builds the receiver without its constructor, which skips a guard the patch added there.

    python scripts/patch_rule.py RUN_DIR GROUND_TRUTH FIXED_DIR ESBMC [--out RUN_DIR/regra_do_patch.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research_pipeline.v2_evaluator import expressions_equivalent
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.loop import verify_hypothesis

KEPT = {"CONFIRMED", "OTHER_FAILURE"}


class ReplayedSpec:
    """Answers every spec request with the spec the buggy run ended on."""

    def __init__(self, spec: str) -> None:
        self.spec = spec

    def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> SynthResult:
        return SynthResult(harness=self.spec, raw_response=self.spec, model="saved-spec")


def bug_of(result: dict, items: list[dict]) -> tuple[str, bool] | None:
    """The labelled bug whose function this hypothesis is in, and whether its expression is the bug's own."""
    h = result["hypothesis"]
    for item in items:
        if Path(h["file"]).name == item["file"] and h["function"] in {f.strip() for f in item["function"].split("/")}:
            own = expressions_equivalent(item["expression"], h["suspect_expression"])
            return item["id"], own
    return None


def classify(on_buggy: str, on_fixed: str) -> str:
    if on_buggy not in KEPT:
        return "nao_aplica"
    if on_fixed == on_buggy:
        return "falha_igual_nas_duas"
    if on_fixed == "NOT_CONFIRMED":
        return "o_patch_corrige"
    # GROUNDING_FAILED: the patch rewrote the line, so the expression is gone. Others: the fixed file could not be run.
    return "linha_reescrita_pelo_patch" if on_fixed == "GROUNDING_FAILED" else "nao_medido"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir")
    parser.add_argument("ground_truth")
    parser.add_argument("fixed_dir")
    parser.add_argument("esbmc")
    parser.add_argument("--out")
    args = parser.parse_args()
    run = Path(args.run_dir)
    report = json.loads((run / "v2_verify_report.json").read_text())
    payload = json.loads(Path(args.ground_truth).read_text())
    items = payload if isinstance(payload, list) else payload.get("items") or list(payload.values())
    rows = []
    for result in report["results"]:
        if result["verdict"] not in KEPT:
            continue
        found = bug_of(result, items)
        if found is None:
            continue
        attempts = result.get("attempts") or []
        spec = next((a["spec"] for a in reversed(attempts) if a.get("spec")), "")
        h = BugHypothesis(**{k: v for k, v in result["hypothesis"].items()
                             if k in {"file", "function", "suspect_expression", "line", "trigger_condition",
                                      "category", "oracle"}})
        fixed_path = Path(args.fixed_dir) / Path(h.file).name
        if not spec or not fixed_path.exists():
            rows.append({"bug": found[0], "own_expression": found[1], "expression": h.suspect_expression,
                         "buggy": result["verdict"], "fixed": "sem_spec_ou_arquivo", "rule": "nao_medido"})
            continue
        print(f"{found[0]} {h.function} :: {h.suspect_expression[:50]}", flush=True)
        done = verify_hypothesis(h, llm=ReplayedSpec(spec), source=fixed_path.read_text(errors="replace"),
                                 esbmc_command=[args.esbmc], bound=5, timeout_seconds=180,
                                 work_dir=run / "regra_do_patch_programs", max_repairs=0)
        rows.append({"bug": found[0], "own_expression": found[1], "expression": h.suspect_expression,
                     "exception": (result.get("replay") or {}).get("exception_type"), "buggy": result["verdict"],
                     "fixed": done.verdict, "rule": classify(result["verdict"], done.verdict)})
    out = Path(args.out) if args.out else run / "regra_do_patch.json"
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    for row in rows:
        print(row["bug"], "própria" if row["own_expression"] else "outra linha", row["buggy"], "->", row["fixed"],
              row["rule"], "|", row["expression"][:45])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
