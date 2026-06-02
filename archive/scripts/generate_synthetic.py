#!/usr/bin/env python3
"""
Generate synthetic test cases for division_by_zero and out_of_bounds.

These complement BugsInPy cases with controlled, ESBMC-verifiable examples
designed to exercise specific patterns the pipeline should detect.

Usage:
    python scripts/generate_synthetic.py
    python scripts/generate_synthetic.py --output-dir examples/labeled/ok --gt-dir examples/labeled/ground_truths/bugs
"""

import argparse
import json
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path("examples/labeled/ok")
GROUND_TRUTH_DIR = Path("examples/labeled/ground_truths/bugs")

# ── synthetic case definitions ────────────────────────────────────────────────
#
# Each entry: (filename_stem, function_name, source_code, gt_entry_fields)
# gt_entry_fields override/supplement defaults.

SYNTHETIC_CASES = [
    # ── division_by_zero ──────────────────────────────────────────────────
    {
        "category": "division_by_zero",
        "stem": "synthetic_div_zero_simple",
        "source": """\
def divide(numerator: int, denominator: int) -> float:
    return numerator / denominator
""",
        "gt": {
            "id": "synthetic_div_zero_simple",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S01",
            "function": "divide",
            "expected_label": "bug",
            "expected_category": "division_by_zero",
            "expected_type": "suspected_bug",
            "line": 2,
            "expression": "numerator / denominator",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Simplest possible division by zero: denominator is unconstrained.",
        },
    },
    {
        "category": "division_by_zero",
        "stem": "synthetic_div_zero_computed_denom",
        "source": """\
def compute_rate(total: int, duration: int) -> float:
    elapsed = duration - 1
    return total / elapsed
""",
        "gt": {
            "id": "synthetic_div_zero_computed_denom",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S02",
            "function": "compute_rate",
            "expected_label": "bug",
            "expected_category": "division_by_zero",
            "expected_type": "suspected_bug",
            "line": 3,
            "expression": "total / elapsed",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Denominator derived from arithmetic: zero when duration==1.",
        },
    },
    {
        "category": "division_by_zero",
        "stem": "synthetic_div_zero_normalize",
        "source": """\
def normalize(value: int, min_val: int, max_val: int) -> float:
    return (value - min_val) / (max_val - min_val)
""",
        "gt": {
            "id": "synthetic_div_zero_normalize",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S03",
            "function": "normalize",
            "expected_label": "bug",
            "expected_category": "division_by_zero",
            "expected_type": "suspected_bug",
            "line": 2,
            "expression": "(value - min_val) / (max_val - min_val)",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Range normalization: zero when max_val == min_val (matplotlib/30 pattern).",
        },
    },
    {
        "category": "division_by_zero",
        "stem": "synthetic_div_zero_step",
        "source": """\
def chunk_count(total_size: int, step_size: int) -> int:
    return total_size // step_size
""",
        "gt": {
            "id": "synthetic_div_zero_step",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S04",
            "function": "chunk_count",
            "expected_label": "bug",
            "expected_category": "division_by_zero",
            "expected_type": "suspected_bug",
            "line": 2,
            "expression": "total_size // step_size",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Integer floor division: zero when step_size==0 (aws-neuron pattern).",
        },
    },
    # ── out_of_bounds ─────────────────────────────────────────────────────
    {
        "category": "out_of_bounds",
        "stem": "synthetic_oob_list_index",
        "source": """\
def get_element(items: list, index: int):
    return items[index]
""",
        "gt": {
            "id": "synthetic_oob_list_index",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S05",
            "function": "get_element",
            "expected_label": "bug",
            "expected_category": "out_of_bounds",
            "expected_type": "suspected_bug",
            "line": 2,
            "expression": "items[index]",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Direct unconstrained index access.",
        },
    },
    {
        "category": "out_of_bounds",
        "stem": "synthetic_oob_first_element",
        "source": """\
def get_first(items: list):
    return items[0]
""",
        "gt": {
            "id": "synthetic_oob_first_element",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S06",
            "function": "get_first",
            "expected_label": "bug",
            "expected_category": "out_of_bounds",
            "expected_type": "suspected_bug",
            "line": 2,
            "expression": "items[0]",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Access index 0 without checking list is non-empty (thefuck pattern).",
        },
    },
    {
        "category": "out_of_bounds",
        "stem": "synthetic_oob_last_element",
        "source": """\
def get_last(items: list):
    return items[-1]
""",
        "gt": {
            "id": "synthetic_oob_last_element",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S07",
            "function": "get_last",
            "expected_label": "bug",
            "expected_category": "out_of_bounds",
            "expected_type": "suspected_bug",
            "line": 2,
            "expression": "items[-1]",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Negative index on potentially empty list.",
        },
    },
    {
        "category": "out_of_bounds",
        "stem": "synthetic_oob_split_access",
        "source": """\
def extract_value(data: str) -> str:
    parts = data.split("=")
    return parts[1]
""",
        "gt": {
            "id": "synthetic_oob_split_access",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S08",
            "function": "extract_value",
            "expected_label": "bug",
            "expected_category": "out_of_bounds",
            "expected_type": "suspected_bug",
            "line": 3,
            "expression": "parts[1]",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "Split then index: fails if delimiter not present (scrapy/18 pattern).",
        },
    },
    {
        "category": "out_of_bounds",
        "stem": "synthetic_oob_pop",
        "source": """\
def remove_at(items: list, index: int) -> list:
    items.pop(index)
    return items
""",
        "gt": {
            "id": "synthetic_oob_pop",
            "source_dataset": "synthetic",
            "source_project": "synthetic",
            "source_bug_id": "S09",
            "function": "remove_at",
            "expected_label": "bug",
            "expected_category": "out_of_bounds",
            "expected_type": "suspected_bug",
            "line": 2,
            "expression": "items.pop(index)",
            "verifiable": True,
            "should_go_to_esbmc": True,
            "confidence": "high",
            "description": "pop() with unconstrained index (thefuck/9 pattern).",
        },
    },
]


def load_gt(gt_path: Path) -> dict:
    if gt_path.exists():
        return json.loads(gt_path.read_text())
    category = gt_path.stem
    return {
        "dataset_name": f"python-bugs-{category}",
        "category": category,
        "total_items": 0,
        "items": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--gt-dir", type=Path, default=GROUND_TRUTH_DIR)
    args = parser.parse_args()

    gts: dict[str, dict] = {}
    written = 0

    for case in SYNTHETIC_CASES:
        category = case["category"]
        stem = case["stem"]
        py_dir = args.output_dir / "bugs" / category
        py_dir.mkdir(parents=True, exist_ok=True)

        py_path = py_dir / f"{stem}.py"
        py_path.write_text(case["source"])
        print(f"[write] {py_path}")

        gt = gts.setdefault(category, load_gt(args.gt_dir / f"{category}.json"))
        existing_ids = {item["id"] for item in gt["items"]}
        entry_id = case["gt"]["id"]
        if entry_id in existing_ids:
            print(f"[skip]  {entry_id} already in ground truth")
            continue

        entry = {**case["gt"], "file": f"{stem}.py"}
        gt["items"].append(entry)
        written += 1

    for category, gt in gts.items():
        gt["total_items"] = len(gt["items"])
        gt_path = args.gt_dir / f"{category}.json"
        gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False))
        print(f"[gt]    {gt_path}")

    print(f"\nDone: {written} new ground truth entries across {len(gts)} categories.")


if __name__ == "__main__":
    main()
