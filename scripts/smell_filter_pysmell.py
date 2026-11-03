"""Measure the LLM smell filter on PySmell's hand labels (dataset/code_smell/pysmell_manual.jsonl).

Candidates are the items either PySmell heuristic reported; the score compares the tool alone with the tool
plus the LLM against the human labels. With ``--sample`` only the drawn candidates are scored, so recall says
how many real smells the LLM drops. Without ``--yes`` it only counts the calls.

    python scripts/smell_filter_pysmell.py --out artifacts/smells/pysmell-200 --sample 200 --yes
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.smells.filter import (
    SmellCandidate,
    filter_candidates,
    score,
)

DATASET = ROOT / "dataset" / "code_smell" / "pysmell_manual.jsonl"
_HEURISTICS = {"tool_experience_based": "experience", "tool_statistics_based": "statistics"}


def pysmell_candidates(rows: list[dict]) -> tuple[list[SmellCandidate], dict[str, tuple[str, int]]]:
    candidates = []
    for row in rows:
        heuristics = [name for field, name in _HEURISTICS.items() if row.get(field)]
        if heuristics:
            candidates.append(SmellCandidate(row["id"], row["smell"], row["path"], row["line"],
                                             "pysmell:" + "+".join(heuristics), row.get("metrics") or {},
                                             row.get("snippet") or "", row.get("snippet_start") or 1))
    return candidates, {row["id"]: (row["smell"], row["label"]) for row in rows}


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sample", type=int, default=0, help="draw this many candidates (0: all)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--backend", default="claude_cli")
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--yes", action="store_true", help="spend the LLM calls")
    args = parser.parse_args()
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    candidates, labels = pysmell_candidates(rows)
    if args.sample:
        candidates = random.Random(args.seed).sample(candidates, min(args.sample, len(candidates)))
        labels = {c.id: labels[c.id] for c in candidates}
    calls = len({(c.path, c.code) for c in candidates if c.code.strip()})
    print(f"{len(candidates)} candidatos, {sum(1 for c in candidates if not c.code.strip())} sem código; "
          f"{calls} chamada(s) ao LLM ({args.backend}).")
    if not args.yes:
        print("Simulação: rode com --yes para gastar as chamadas.")
        return 0
    from research_pipeline.verify.llm_client import LLMClient

    args.out.mkdir(parents=True, exist_ok=True)
    results_path = args.out / "results.json"
    done = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
    llm = LLMClient(backend=args.backend, model=args.model, timeout_seconds=300)
    results = filter_candidates(candidates, llm, done=done, on_answer=lambda r: _write(results_path, r))
    _write(results_path, results)
    report = {"sample": args.sample, "seed": args.seed, "backend": args.backend, "model": args.model,
              **score(candidates, labels, results)}
    _write(args.out / "score.json", report)
    print(json.dumps({k: report[k] for k in ("tool", "tool_llm", "llm_errors", "no_code")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
