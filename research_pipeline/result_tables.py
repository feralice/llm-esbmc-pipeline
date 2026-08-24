from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Iterable


def category_rows(report_paths: Iterable[str | Path]) -> list[dict]:
    """Build deterministic per-model/category rows from benchmark reports."""
    rows: list[dict] = []
    for path_like in report_paths:
        path = Path(path_like)
        report = json.loads(path.read_text(encoding="utf-8"))
        model = str(report.get("model") or path.stem)
        sections = (
            ("llm", report.get("per_category_llm", report.get("per_category", {}))),
            ("hybrid", report.get("per_category_hybrid", {})),
        )
        for flow, categories in sections:
            if not isinstance(categories, dict):
                continue
            for category, counts in categories.items():
                tp = int(counts.get("tp", 0))
                fp = int(counts.get("fp", 0))
                fn = int(counts.get("fn", 0))
                precision, recall, f1 = _prf(tp, fp, fn)
                rows.append({
                    "model": model,
                    "flow": flow,
                    "category": category,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                })
    return sorted(rows, key=lambda row: (row["model"], row["flow"], row["category"]))


def rows_to_csv(rows: list[dict]) -> str:
    output = io.StringIO()
    fields = ["model", "flow", "category", "tp", "fp", "fn", "precision", "recall", "f1"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def rows_to_markdown(rows: list[dict]) -> str:
    header = "| Modelo | Fluxo | Categoria | TP | FP | FN | P | R | F1 |"
    separator = "|---|---|---|---:|---:|---:|---:|---:|---:|"
    body = [
        "| {model} | {flow} | {category} | {tp} | {fp} | {fn} | {precision:.4f} | {recall:.4f} | {f1:.4f} |".format(**row)
        for row in rows
    ]
    return "\n".join([header, separator, *body]) + "\n"


def rows_to_latex(rows: list[dict]) -> str:
    lines = [
        r"\begin{tabular}{lllrrrrrr}",
        r"\hline",
        r"Modelo & Fluxo & Categoria & TP & FP & FN & P & R & F1 \\",
        r"\hline",
    ]
    for row in rows:
        values = [
            _latex_escape(str(row["model"])),
            _latex_escape(str(row["flow"])),
            _latex_escape(str(row["category"])),
            str(row["tp"]), str(row["fp"]), str(row["fn"]),
            f"{row['precision']:.4f}", f"{row['recall']:.4f}", f"{row['f1']:.4f}",
        ]
        lines.append(" & ".join(values) + r" \\")
    lines.extend([r"\hline", r"\end{tabular}"])
    return "\n".join(lines) + "\n"


def write_category_tables(
    report_paths: Iterable[str | Path], output_dir: str | Path
) -> dict[str, Path]:
    rows = category_rows(report_paths)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "csv": directory / "metrics_by_category.csv",
        "markdown": directory / "metrics_by_category.md",
        "latex": directory / "metrics_by_category.tex",
    }
    outputs["csv"].write_text(rows_to_csv(rows), encoding="utf-8")
    outputs["markdown"].write_text(rows_to_markdown(rows), encoding="utf-8")
    outputs["latex"].write_text(rows_to_latex(rows), encoding="utf-8")
    return outputs


def category_consistency_issues(report_path: str | Path) -> list[dict]:
    """Flag aggregate smell counts that disagree with their three categories."""
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    aggregate = report.get("metrics", {}).get("smells", {})
    per_category = report.get("per_category_llm", report.get("per_category", {}))
    smell_categories = ("long_method", "many_parameters", "complex_conditional")
    issues = []
    for field in ("tp", "fp", "fn"):
        aggregate_value = int(aggregate.get(field, 0))
        category_value = sum(int(per_category.get(category, {}).get(field, 0)) for category in smell_categories)
        if aggregate_value != category_value:
            issues.append({"field": field, "aggregate": aggregate_value, "per_category_sum": category_value})
    return issues


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def _latex_escape(value: str) -> str:
    return value.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("%", r"\%")
