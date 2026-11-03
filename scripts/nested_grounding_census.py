"""How the verify engine grounds each nested function of a repository, without any LLM call.

Each nested function gets a synthetic hypothesis on the first division or subscript of its own body (else its
first return value); the count says how many ground through the enclosing function, how many are hoisted,
how many fail, and how many sit in async code.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.scan.callgraph import build_callgraph
from research_pipeline.verify.astutil import nested_chain
from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis


def _suspect(node: ast.FunctionDef) -> ast.expr | None:
    own = [n for n in ast.walk(node) if isinstance(n, (ast.BinOp, ast.Subscript, ast.Return))]
    risky = [n for n in own if isinstance(n, ast.Subscript) or (isinstance(n, ast.BinOp)
             and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod)))]
    if risky:
        return min(risky, key=lambda n: n.lineno)
    returns = [n.value for n in own if isinstance(n, ast.Return) and n.value is not None]
    return min(returns, key=lambda n: n.lineno) if returns else None


def census(root: Path) -> tuple[Counter, list[dict]]:
    graph = build_callgraph(root)
    counts, rows = Counter(), []
    for function in graph.functions.values():
        if not function.nested:
            continue
        source = (root / function.file).read_text(encoding="utf-8", errors="replace")
        chain = nested_chain(ast.parse(source), function.qualname) or []
        if function.is_async or any(isinstance(n, ast.AsyncFunctionDef) for n in chain):
            counts["async"] += 1
            continue
        node = chain[-1] if chain else None
        suspect = _suspect(node) if isinstance(node, ast.FunctionDef) else None
        if suspect is None:
            counts["no_suspect"] += 1
            continue
        h = BugHypothesis(function.file, function.qualname, ast.unparse(suspect), line=suspect.lineno)
        grounded = ground(h, source)
        if isinstance(grounded, Grounded) and not grounded.unsupported:
            path = next((t.split(":")[0] for t in grounded.transforms if t.startswith("nested_entry_")), "other")
            kind = {"nested_entry_via_outer": "via_outer", "nested_entry_hoisted": "hoisted"}.get(path, "other")
            reason = ""
        else:
            kind, reason = "failed", grounded.unsupported if isinstance(grounded, Grounded) else grounded.reason
        counts[kind] += 1
        rows.append({"function": f"{function.file}::{function.qualname}", "kind": kind, "reason": reason})
    return counts, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--json", type=Path, help="write every nested function with how it grounded")
    args = parser.parse_args()
    counts, rows = census(args.repo)
    print(json.dumps(dict(sorted(counts.items()))))
    if args.json:
        args.json.write_text(json.dumps({"counts": counts, "functions": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
