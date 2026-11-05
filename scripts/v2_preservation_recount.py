"""Recount, without ESBMC or an LLM, how many stored harnesses keep the target function: agent-arm cases
(``harness_path`` with ``original.py`` beside it) and engine results (``program_path``, original from the
dataset's full files, the fixed ones for a ``control-fixed`` run). ``--src`` runs another version of the
check, e.g. an older commit unpacked with ``git archive <commit> src | tar -x -C <dir>``.

  python scripts/v2_preservation_recount.py [--src <dir>/src] [--out recount.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _records(data: object, key: str):
    if isinstance(data, dict):
        if key in data and isinstance(data.get("hypothesis"), dict):
            yield data
        for value in data.values():
            yield from _records(value, key)
    elif isinstance(data, list):
        for value in data:
            yield from _records(value, key)


def _cases(artifacts: Path, checked: frozenset[str], replay_program_path):
    seen = set()
    for path in sorted(artifacts.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        for record in _records(data, "harness_path"):
            harness = Path(record["harness_path"])
            if harness.exists() and (harness.parent / "original.py").exists() and ("agent", harness) not in seen:
                seen.add(("agent", harness))
                yield "agent", str(path), harness.parent / "original.py", harness, record["hypothesis"]
        for record in _records(data, "program_path"):
            if record.get("verdict") not in checked or not record.get("program_path"):
                continue
            program = replay_program_path(record)
            hypothesis = record["hypothesis"]
            folder = "arquivo_corrigido" if "control-fixed" in str(path) else "arquivo_com_bug"
            original = ROOT / "dataset/bugs_reais" / folder / Path(hypothesis["file"]).name
            if program is None or not program.exists() or not original.exists() or ("engine", program) in seen:
                continue
            seen.add(("engine", program))
            yield "engine", str(path), original, program, hypothesis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default=str(ROOT / "src"))
    parser.add_argument("--artifacts", default=str(ROOT / "artifacts"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    sys.path.insert(0, args.src)
    from research_pipeline.verify.validation import (
        _CHECKED,
        replay_program_path,
        target_preserved,
    )

    warnings.filterwarnings("ignore", category=SyntaxWarning)
    rows, counts = [], Counter()
    for kind, report, original, harness, hypothesis in _cases(Path(args.artifacts), frozenset(_CHECKED),
                                                              replay_program_path):
        try:
            kept = target_preserved(original.read_text(encoding="utf-8"), harness.read_text(encoding="utf-8"),
                                    hypothesis["function"], hypothesis.get("suspect_expression", ""))
        except SyntaxError:
            continue
        counts[kind, kept] += 1
        rows.append({"kind": kind, "report": report, "harness": str(harness), "function": hypothesis["function"],
                     "preserved": kept})
    for (kind, kept), number in sorted(counts.items()):
        print(f"{kind}: {'preserved' if kept else 'changed'} {number}")
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
