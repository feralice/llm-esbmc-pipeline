"""Print the V2 detection prompts (system and user) without calling any LLM.

Usage: .venv/bin/python scripts/print_detection_prompt.py --input FILE_OR_DIR... [--v2-variants A1,A2,A13]
       [--example-pool dataset/bugs_reais/ground_truths.json] [--example-k 3] [--context-sources DIR]
       [--function QUALNAME] [--out DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from research_pipeline.llm.example_pool import load_example_pool
from research_pipeline.llm.prompts import (
    build_user_prompt,
    load_system_prompt,
    set_context_sources,
    set_example_pool,
)
from research_pipeline.preprocess import preprocess_file

CHARS_PER_TOKEN = 4  # rough, only to compare the variants' size


def _python_files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        path = Path(raw)
        out.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    return out


def render(paths: list[str], variants: tuple[str, ...], *,
           function: str | None = None) -> tuple[str, list[tuple[str, str]]]:
    system = load_system_prompt(include_smells=False, v2_detection=True, v2_variants=variants)
    users = [(f"{path.name}::{unit.qualname}", build_user_prompt(unit, include_smells=False, v2_variants=variants))
             for path in _python_files(paths) for unit in preprocess_file(path)
             if function is None or unit.qualname == function]
    return system, users


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--v2-variants", default="")
    parser.add_argument("--example-pool", default=str(REPO_ROOT / "dataset/bugs_reais/ground_truths.json"))
    parser.add_argument("--example-k", type=int, default=3)
    parser.add_argument("--context-sources", default=None)
    parser.add_argument("--function", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    variants = tuple(v for v in args.v2_variants.split(",") if v)
    set_context_sources(Path(args.context_sources) if args.context_sources else None)
    if "A13" in variants:
        set_example_pool(load_example_pool(Path(args.example_pool)), k=args.example_k)
    try:
        system, users = render(args.input, variants, function=args.function)
    finally:
        set_context_sources(None)
        set_example_pool(None)
    if not users:
        print("Nenhuma função encontrada.", file=sys.stderr)
        return 1
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "system.txt").write_text(system, encoding="utf-8")
        for label, user in users:
            (out / f"{label.replace('::', '__')}.txt").write_text(user, encoding="utf-8")
    else:
        print(f"=== system ===\n{system}\n")
        for label, user in users:
            print(f"=== {label} ===\n{user}\n")
    total = sum(len(system) + len(user) for _, user in users)
    print(f"{len(users)} função(ões); cerca de {total // CHARS_PER_TOKEN} tokens de entrada no total",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
