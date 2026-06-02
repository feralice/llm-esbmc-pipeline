#!/usr/bin/env python3
"""
Validate all labeled examples in examples/labeled/ok/ by running the pipeline
and comparing results against ground_truth JSON files.

Runs without ESBMC by default (LLM-only). Pass --with-esbmc to include
formal verification step.

Usage:
    source .venv/bin/activate

    # LLM-only validation (fast):
    python scripts/validate_dataset.py --llm-backend anthropic

    # Full validation with ESBMC:
    python scripts/validate_dataset.py --llm-backend anthropic --with-esbmc --esbmc-command esbmc --python

    # Validate only specific categories:
    python scripts/validate_dataset.py --categories division_by_zero out_of_bounds

    # Limit to N files per category (useful for quick smoke test):
    python scripts/validate_dataset.py --limit 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from research_pipeline.pipeline import run_pipeline
from research_pipeline.models import FinalResult

LABELED_OK_DIR = REPO_ROOT / "examples" / "labeled" / "ok" / "bugs"
GT_DIR = REPO_ROOT / "examples" / "labeled" / "ground_truths" / "bugs"


# ── ground truth loading ──────────────────────────────────────────────────────

def load_ground_truths(gt_dir: Path, categories: list[str]) -> dict[str, dict]:
    """Return {filename: gt_entry} for all items in all category JSONs."""
    index: dict[str, dict] = {}
    for cat in categories:
        gt_path = gt_dir / f"{cat}.json"
        if not gt_path.exists():
            continue
        data = json.loads(gt_path.read_text())
        for item in data.get("items", []):
            index[item["file"]] = item
    return index


# ── per-file validation ───────────────────────────────────────────────────────

def validate_file(
    py_path: Path,
    gt_entry: dict,
    backend: str,
    model: str,
    anthropic_key: str | None,
    openai_key: str | None,
    ollama_url: str,
    with_esbmc: bool,
    esbmc_cmd: list[str],
    output_dir: Path,
) -> dict:
    """Run the pipeline on one file and return a result record."""
    start = time.time()
    expected_cat = gt_entry.get("expected_category", "")

    try:
        final: list[FinalResult] = run_pipeline(
            input_path=py_path,
            output_dir=output_dir / py_path.stem,
            esbmc_command=esbmc_cmd if with_esbmc else None,
            backend=backend,
            llm_model=model,
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            ollama_base_url=ollama_url,
        )
    except Exception as e:
        return _error_record(py_path, gt_entry, str(e))

    elapsed = time.time() - start
    detected_cats = [r.finding.category for r in final if r.finding and r.finding.category]
    classifications = [r.final_classification for r in final]
    hit = expected_cat in detected_cats

    return {
        "file": py_path.name,
        "category": expected_cat,
        "confidence_gt": gt_entry.get("confidence", "?"),
        "needs_review": gt_entry.get("needs_manual_review", False),
        "expected_label": gt_entry.get("expected_label", "bug"),
        "detected_categories": detected_cats,
        "hit": hit,
        "pipeline_classifications": classifications,
        "elapsed_s": round(elapsed, 1),
        "llm_findings": len(final),
    }


def _error_record(py_path: Path, gt_entry: dict, reason: str) -> dict:
    return {
        "file": py_path.name,
        "category": gt_entry.get("expected_category", ""),
        "confidence_gt": gt_entry.get("confidence", "?"),
        "needs_review": gt_entry.get("needs_manual_review", False),
        "expected_label": gt_entry.get("expected_label", "bug"),
        "detected_categories": [],
        "hit": False,
        "pipeline_classifications": [f"error: {reason}"],
        "elapsed_s": 0.0,
        "llm_findings": 0,
    }


# ── summary printing ──────────────────────────────────────────────────────────

def print_summary(results: list[dict]) -> None:
    print(f"\n{'='*70}")
    print(f"  Validation Summary  ({len(results)} files)")
    print(f"{'='*70}")

    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    total_hit = 0
    total_all = 0

    for cat, items in sorted(by_cat.items()):
        hits = sum(1 for r in items if r["hit"])
        skipped = sum(1 for r in items if r["needs_review"])
        reviewed = len(items) - skipped
        total_hit += hits
        total_all += reviewed
        pct = hits / reviewed * 100 if reviewed else 0
        print(f"\n  [{cat.upper()}]  {hits}/{reviewed} detected  ({pct:.0f}%)  "
              f"[{skipped} stubs skipped]")

        for r in sorted(items, key=lambda x: (not x["hit"], x["file"])):
            flag = "✓" if r["hit"] else ("~" if r["needs_review"] else "✗")
            cats = ", ".join(r["detected_categories"][:3]) or "—"
            clsf = ", ".join(r["pipeline_classifications"][:2]) or "—"
            print(f"    {flag} {r['file'][:45]:47s} "
                  f"det={cats[:25]:27s} cls={clsf[:20]:20s} ({r['elapsed_s']}s)")

    print(f"\n{'─'*70}")
    overall_pct = total_hit / total_all * 100 if total_all else 0
    print(f"  Overall detection rate: {total_hit}/{total_all}  ({overall_pct:.0f}%)")
    print(f"  (Stubs with needs_manual_review=true are excluded from rate)\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--llm-backend", choices=["openai", "anthropic", "ollama"],
                        default="anthropic")
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--anthropic-api-key", default=None)
    parser.add_argument("--openai-api-key", default=None)
    parser.add_argument("--ollama-base-url", default="http://localhost:11434/v1")
    parser.add_argument("--with-esbmc", action="store_true",
                        help="Also run ESBMC formal verification step")
    parser.add_argument("--esbmc-command", nargs="+", default=["esbmc", "--python"],
                        metavar="CMD")
    parser.add_argument("--categories", nargs="+",
                        default=["division_by_zero", "out_of_bounds", "assertion_violation"],
                        help="Which bug categories to validate")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max files per category (for quick smoke tests)")
    parser.add_argument("--skip-stubs", action="store_true", default=True,
                        help="Skip files with needs_manual_review=true (default: on)")
    parser.add_argument("--include-stubs", dest="skip_stubs", action="store_false",
                        help="Include stub files in validation")
    parser.add_argument("--output-json", type=Path, default=None,
                        help="Save full results as JSON")
    args = parser.parse_args()

    # Resolve API keys
    anthropic_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")

    default_models = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-6", "ollama": "llama3.2"}
    model = args.llm_model or default_models[args.llm_backend]

    print(f"[config] backend={args.llm_backend}  model={model}  "
          f"esbmc={'yes' if args.with_esbmc else 'no'}")

    gt_index = load_ground_truths(GT_DIR, args.categories)

    results: list[dict] = []
    output_dir = REPO_ROOT / "output" / "validate"
    output_dir.mkdir(parents=True, exist_ok=True)

    for category in args.categories:
        cat_dir = LABELED_OK_DIR / category
        if not cat_dir.exists():
            print(f"[skip]  {cat_dir} not found")
            continue

        files = sorted(cat_dir.glob("*.py"))
        if args.limit:
            files = files[: args.limit]

        print(f"\n[{category}]  {len(files)} files")
        for py_path in files:
            gt_entry = gt_index.get(py_path.name)
            if gt_entry is None:
                print(f"  [warn] no GT entry for {py_path.name} — skipping")
                continue
            if args.skip_stubs and gt_entry.get("needs_manual_review"):
                print(f"  [stub] {py_path.name} — skipped (needs_manual_review)")
                continue

            print(f"  [run]  {py_path.name} ...", end=" ", flush=True)
            r = validate_file(
                py_path, gt_entry,
                backend=args.llm_backend,
                model=model,
                anthropic_key=anthropic_key,
                openai_key=openai_key,
                ollama_url=args.ollama_base_url,
                with_esbmc=args.with_esbmc,
                esbmc_cmd=args.esbmc_command,
                output_dir=output_dir,
            )
            results.append(r)
            flag = "✓" if r["hit"] else "✗"
            print(f"{flag}  ({r['elapsed_s']}s)")

    print_summary(results)

    if args.output_json:
        args.output_json.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"[json]  {args.output_json}")


if __name__ == "__main__":
    main()
