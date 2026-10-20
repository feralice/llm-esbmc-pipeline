"""LLM as judge over a finished detection run (step 7 of docs/projeto/PLANO_2026-10-19.md).

One call per function: the judge sees the code and the detector's hypotheses, and for each one must build a
concrete input that gets past the function's guards and causes the failure (evidence-based judging, Du et al.,
ICSE-SEIP 2026). A hypothesis it cannot back with an input scores low; the report shows bugs at the line and
precision when only the hypotheses above each threshold are kept. A failed judge call keeps every hypothesis.

    python scripts/v2_judge.py artifacts/v2/det-2026-10-17-amostra-A1,A2 --out artifacts/v2/juiz-<tag>
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402
from research_pipeline.verify.astutil import find_function  # noqa: E402
from research_pipeline.verify.hypothesis import undo_prompt_rename  # noqa: E402
from research_pipeline.verify.llm_client import LLMClient  # noqa: E402

THRESHOLDS = (0.0, 0.3, 0.5, 0.7)
SYSTEM = """Você revisa suspeitas de bug em código Python real. Para cada hipótese, tente construir uma entrada
concreta (valores das variáveis e do objeto) que passe pelas guardas da função, chegue à linha suspeita e cause
a falha descrita. Se a entrada existir, real=true e escreva-a em "input". Se as guardas, os tipos ou o fluxo
impedem a falha, real=false e diga por quê. Não invente código que não está na função. Responda só com JSON:
{"verdicts": [{"index": 0, "real": true, "confidence": 0.0-1.0, "input": "...", "why": "..."}]}"""


def parse_scores(reply: str, count: int) -> list[float | None]:
    """A score in [0, 1] per hypothesis: confidence that it is real, halved when no concrete input backs it."""
    scores: list[float | None] = [None] * count
    try:
        verdicts = json.loads(reply).get("verdicts", [])
    except (json.JSONDecodeError, AttributeError):
        return scores
    for verdict in verdicts if isinstance(verdicts, list) else []:
        try:
            index, confidence = int(verdict["index"]), min(max(float(verdict.get("confidence", 0.5)), 0.0), 1.0)
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= index < count:
            continue
        if verdict.get("real"):
            scores[index] = confidence if str(verdict.get("input", "")).strip() else confidence / 2
        else:
            scores[index] = round(1.0 - confidence, 6)
    return scores


def metrics(rows: list[dict], threshold: float) -> dict:
    """``score is None`` (the judge failed) keeps the hypothesis."""
    kept = [r for r in rows if r["score"] is None or r["score"] >= threshold]
    at_line = [r for r in kept if r["at_line"]]
    return {"threshold": threshold, "kept": len(kept), "bugs_at_line": len({r["bug"] for r in at_line}),
            "precision": len(at_line) / len(kept) if kept else None}


def _function_code(path: Path, qualname: str) -> str:
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        node = find_function(ast.parse(source), qualname)
    except SyntaxError:
        node = None
    return (ast.get_source_segment(source, node) if node is not None else None) or source


def _prompt(code: str, candidates: list[dict]) -> str:
    listed = "\n".join(f"{i}. linha suspeita: {c['expression']}\n   falha: {c.get('violated_property', '')}\n"
                       f"   gatilho: {c.get('note', '')[:400]}" for i, c in enumerate(candidates))
    return f"Código:\n```python\n{code}\n```\n\nHipóteses:\n{listed}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="detection run folder with v2_checkpoint.json")
    parser.add_argument("--sample", default="dataset/bugs_reais/amostra_deteccao.json")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--backend", default="claude_cli")
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    items = {i["id"]: i for i in json.loads((ROOT / args.ground_truth).read_text(encoding="utf-8"))["items"]}
    sample = {Path(f).stem for f in json.loads((ROOT / args.sample).read_text(encoding="utf-8"))["files"]}
    sample = {b for b in sample if "behaviour_change" not in items[b]}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "judge_checkpoint.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    llm = LLMClient(backend=args.backend, model=args.model, timeout_seconds=600)
    units = json.loads((Path(args.run) / "v2_checkpoint.json").read_text(encoding="utf-8"))["detection_units"]
    rows = []
    for key, unit in units.items():
        candidates = [c for c in unit.get("candidates", []) if Path(c["file"]).stem in sample]
        if not candidates:
            continue
        if key not in state:
            code = _function_code(ROOT / candidates[0]["file"], candidates[0]["function"])
            try:
                reply = llm.complete(SYSTEM, _prompt(code, candidates), json_mode=True).harness
            except Exception as exc:  # noqa: BLE001 - a failed call keeps the hypotheses and the batch goes on
                reply = f"error: {exc}"
            state[key] = {"reply": reply, "scores": parse_scores(reply, len(candidates))}
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{Path(key.split('::')[0]).name}::{key.split('::')[-1]} -> {state[key]['scores']}", flush=True)
        for candidate, score in zip(candidates, state[key]["scores"]):
            bug = Path(candidate["file"]).stem
            hypothesis = {"function": candidate["function"],
                          "suspect_expression": undo_prompt_rename(candidate["expression"], candidate["function"])}
            rows.append({"bug": bug, "expression": candidate["expression"], "score": score,
                         "at_line": at_bug_line(hypothesis, items[bug])})
    report = {"run": str(args.run), "hypotheses": len(rows), "metrics": [metrics(rows, t) for t in THRESHOLDS],
              "rows": rows}
    (out / "juiz.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for m in report["metrics"]:
        print(m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
