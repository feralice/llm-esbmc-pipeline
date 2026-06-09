from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_TEMPLATE = ROOT / "frontend" / "index.html"


def _safe_script_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_benchmark_reports(directory: Path) -> list[dict[str, object]]:
    reports = []
    for path in sorted(directory.glob("benchmark_*.json")):
        if path.name == "benchmark_matrix_manifest.json":
            continue
        data = _load_json(path)
        if isinstance(data, dict) and "metrics" in data:
            reports.append({"name": path.name, "data": data})
    return reports


def build_html_report(
    *,
    benchmark_dir: Path,
    output_path: Path,
    report_path: Path | None = None,
) -> Path:
    """Build a self-contained static dashboard from benchmark JSON reports."""

    payload: dict[str, object] = {
        "benchmarks": _collect_benchmark_reports(benchmark_dir),
    }
    if report_path and report_path.exists():
        report_data = _load_json(report_path)
        if isinstance(report_data, dict) and "metrics" in report_data:
            payload["benchmarks"].append({"name": report_path.name, "data": report_data})
        else:
            payload["report"] = report_data

    html = FRONTEND_TEMPLATE.read_text(encoding="utf-8")
    preload = (
        "<script>\n"
        f"window.__LLM_ESBMC_PRELOADED__ = {_safe_script_json(payload)};\n"
        "</script>\n"
    )
    html = html.replace("<script>\n// =================== STATE ===================", preload + "<script>\n// =================== STATE ===================", 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a static HTML dashboard for benchmark results.")
    parser.add_argument("--benchmark-dir", default="reports/json/v1_benchmark")
    parser.add_argument("--output", default="reports/html/benchmark_dashboard.html")
    parser.add_argument("--report", default=None, help="Optional full_report.json/report.json to embed")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output = build_html_report(
        benchmark_dir=(ROOT / args.benchmark_dir).resolve(),
        output_path=(ROOT / args.output).resolve(),
        report_path=(ROOT / args.report).resolve() if args.report else None,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
