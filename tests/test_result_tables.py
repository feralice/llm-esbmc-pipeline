import json

from research_pipeline.result_tables import (
    category_consistency_issues,
    category_rows,
    rows_to_csv,
    rows_to_latex,
    rows_to_markdown,
)


def _report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({
        "model": "model_a",
        "metrics": {"smells": {"tp": 1, "fp": 2, "fn": 0}},
        "per_category_llm": {
            "long_method": {"tp": 1, "fp": 1, "fn": 0},
            "many_parameters": {"tp": 0, "fp": 2, "fn": 0},
        },
        "per_category_hybrid": {"out_of_bounds": {"tp": 2, "fp": 0, "fn": 1}},
    }), encoding="utf-8")
    return path


def test_category_rows_recompute_metrics(tmp_path) -> None:
    rows = category_rows([_report(tmp_path)])
    row = next(row for row in rows if row["category"] == "out_of_bounds")
    assert row["flow"] == "hybrid"
    assert row["precision"] == 1.0
    assert row["recall"] == 0.6667
    assert row["f1"] == 0.8


def test_category_tables_render_three_formats(tmp_path) -> None:
    rows = category_rows([_report(tmp_path)])
    assert rows_to_csv(rows).startswith("model,flow,category")
    assert "| Modelo |" in rows_to_markdown(rows)
    assert "model\\_a" in rows_to_latex(rows)


def test_consistency_check_finds_aggregate_mismatch(tmp_path) -> None:
    issues = category_consistency_issues(_report(tmp_path))
    assert issues == [{"field": "fp", "aggregate": 2, "per_category_sum": 3}]
