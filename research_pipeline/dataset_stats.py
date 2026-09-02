from __future__ import annotations

import ast
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .evaluator import load_ground_truth_cases
from .preprocess import preprocess_file
from .smell_policy import smell_measurements


def build_dataset_statistics(ground_truth_path: str | Path) -> dict:
    """Measure target functions and summarize distributions by ground-truth category.

    Cyclomatic complexity is operationally defined here as 1 + decision nodes
    (if/for/while/if-expression/except-handler) + boolean and/or connectors.
    """
    cases = load_ground_truth_cases(Path(ground_truth_path))
    function_rows: list[dict] = []
    missing_functions: list[dict] = []

    for source_path, expected in cases:
        units = {unit.name: unit for unit in preprocess_file(source_path)}
        expected_by_function: dict[str, set[str]] = defaultdict(set)
        for entry in expected:
            expected_by_function[str(entry.get("function", ""))].add(str(entry["category"]))
        for function, categories in sorted(expected_by_function.items()):
            unit = units.get(function)
            if unit is None:
                missing_functions.append({"file": str(source_path), "function": function})
                continue
            measures = smell_measurements(unit)
            missing_annotations = [
                parameter for parameter in unit.parameters if parameter not in unit.type_hints
            ]
            if "return" not in unit.type_hints:
                missing_annotations.append("return")
            function_rows.append({
                "file": str(source_path),
                "function": function,
                "categories": sorted(categories),
                "physical_lines": unit.metrics["line_count"],
                "executable_lines": measures["executable_lines"],
                "parameters": measures["parameters"],
                "cyclomatic_complexity": _cyclomatic_complexity(unit.source),
                "missing_type_annotations": missing_annotations,
            })

    metrics = ("physical_lines", "executable_lines", "parameters", "cyclomatic_complexity")
    per_category: dict[str, dict] = {}
    category_names = sorted({category for row in function_rows for category in row["categories"]})
    for category in category_names:
        rows = [row for row in function_rows if category in row["categories"]]
        per_category[category] = {
            "functions": len(rows),
            **{metric: _summary([row[metric] for row in rows]) for metric in metrics},
        }

    return {
        "ground_truth": str(Path(ground_truth_path)),
        "case_count": len(cases),
        "target_function_count": len(function_rows),
        "label_count": sum(len(row["categories"]) for row in function_rows),
        "missing_functions": missing_functions,
        "functions_missing_type_annotations": sum(
            bool(row["missing_type_annotations"]) for row in function_rows
        ),
        "complexity_definition": "1 + decision nodes + boolean and/or connectors",
        "overall": {metric: _summary([row[metric] for row in function_rows]) for metric in metrics},
        "per_category": per_category,
        "functions": function_rows,
    }


def write_dataset_statistics(report: dict, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _cyclomatic_complexity(source: str) -> int:
    tree = ast.parse(source)
    decisions = sum(
        isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler))
        for node in ast.walk(tree)
    )
    boolean_connectors = sum(
        len(node.values) - 1 for node in ast.walk(tree) if isinstance(node, ast.BoolOp)
    )
    return 1 + decisions + boolean_connectors


def _summary(values: list[int]) -> dict:
    if not values:
        return {"min": None, "max": None, "mean": None, "median": None, "stdev": None}
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
    }
