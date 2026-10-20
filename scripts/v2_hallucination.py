"""How often detection hallucinates, judged by the AST alone (no LLM, no ESBMC).

A hypothesis hallucinates when its function is not in the file the model saw, its suspect expression is not in
that function, or the exception it claims cannot come from the operations of that expression. The report also
shows what dropping those hypotheses does to the sample metric: bugs at the line and precision.

    python scripts/v2_hallucination.py artifacts/v2/det-*-amostra-*/ --out <dir>
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402
from research_pipeline.verify.astutil import expression_nodes  # noqa: E402
from research_pipeline.verify.hypothesis import undo_prompt_rename  # noqa: E402

KINDS = ("funcao_inexistente", "expressao_inexistente", "excecao_incompativel")


def _raises_zero_division(node: ast.AST) -> bool:
    return (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "divmod")


def _method(node: ast.AST, *names: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in names


# Only exceptions with a short list of operations that raise them; TypeError, ValueError and the rest are not judged.
_CAN_RAISE = {
    "ZeroDivisionError": _raises_zero_division,
    "IndexError": lambda n: isinstance(n, ast.Subscript) or _method(n, "pop"),
    "KeyError": lambda n: isinstance(n, (ast.Subscript, ast.Delete)) or _method(n, "pop", "remove"),
    "AttributeError": lambda n: isinstance(n, ast.Attribute),
}


def _claimed(candidate: dict) -> str:
    match = re.search(r"\b(\w+Error)\b", f"{candidate.get('violated_property', '')} {candidate.get('note', '')}")
    return match.group(1) if match else ""


def check(candidate: dict, source: str) -> list[str]:
    """The hallucination kinds of one hypothesis; empty when the AST finds nothing wrong."""
    tree = ast.parse(source)
    name = candidate["function"].rsplit(".", 1)[-1]
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if not functions:
        return ["funcao_inexistente"]
    expression = undo_prompt_rename(candidate["expression"], candidate["function"])
    nodes = [n for f in functions for n in expression_nodes(f, expression)]
    if not nodes:
        return ["expressao_inexistente"]
    can_raise = _CAN_RAISE.get(_claimed(candidate))
    inside = [sub for node in nodes for sub in ast.walk(node)]
    # A call may raise anything from inside (getattr, a library method): only call-free code is judged.
    if can_raise and not any(isinstance(sub, ast.Call) for sub in inside) and not any(map(can_raise, inside)):
        return ["excecao_incompativel"]
    return []


def evaluate(run: Path, ground_truth: dict, sample: set[str]) -> dict:
    kinds: Counter = Counter()
    hits_all, hits_kept = set(), set()
    total = kept = at_all = at_kept = 0
    checkpoint = json.loads((run / "v2_checkpoint.json").read_text(encoding="utf-8"))
    for unit in checkpoint["detection_units"].values():
        for candidate in unit.get("candidates", []):
            bug = Path(candidate["file"]).stem
            if bug not in sample:
                continue
            source = (ROOT / candidate["file"]).read_text(encoding="utf-8", errors="replace")
            found = check(candidate, source)
            kinds.update(found)
            hypothesis = {"function": candidate["function"],
                          "suspect_expression": undo_prompt_rename(candidate["expression"], candidate["function"])}
            at = at_bug_line(hypothesis, ground_truth[bug])
            total += 1
            at_all += at
            if at:
                hits_all.add(bug)
            if not found:
                kept += 1
                at_kept += at
                if at:
                    hits_kept.add(bug)
    return {"run": run.name, "hypotheses": total, "hallucinated": total - kept, "kinds": dict(kinds),
            "bugs_at_line": len(hits_all), "bugs_at_line_after_filter": len(hits_kept),
            "lost_by_filter": sorted(hits_all - hits_kept),
            "precision": at_all / total if total else None, "precision_after_filter": at_kept / kept if kept else None}


def render(rows: list[dict], denominator: int) -> str:
    lines = [f"| Rodada | Hipóteses | Alucinadas | {' | '.join(KINDS)} | Bugs na linha ({denominator}) | Depois do filtro | "
             "Precisão | Depois do filtro |", "|---" * (8 + len(KINDS)) + "|"]
    for r in rows:
        kinds = " | ".join(str(r["kinds"].get(k, 0)) for k in KINDS)
        lines.append(f"| {r['run']} | {r['hypotheses']} | {r['hallucinated']} | {kinds} | {r['bugs_at_line']} | "
                     f"{r['bugs_at_line_after_filter']} | {r['precision']:.0%} | {r['precision_after_filter']:.0%} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", help="detection run folders with v2_checkpoint.json")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--sample", default="dataset/bugs_reais/amostra_deteccao.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    items = {i["id"]: i for i in json.loads((ROOT / args.ground_truth).read_text(encoding="utf-8"))["items"]}
    sample = {Path(f).stem for f in json.loads((ROOT / args.sample).read_text(encoding="utf-8"))["files"]}
    sample = {b for b in sample if "behaviour_change" not in items[b]}
    rows = [evaluate(Path(r), items, sample) for r in args.runs if (Path(r) / "v2_checkpoint.json").exists()]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "alucinacao.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "alucinacao.md").write_text(render(rows, len(sample)), encoding="utf-8")
    print(render(rows, len(sample)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
