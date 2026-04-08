from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_pipeline.pipeline import run_pipeline


def test_pipeline_generates_mixed_results(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        "\n".join(
            [
                "def avg(values, n):",
                "    total = 0",
                "    for i in range(n):",
                "        total += values[i]",
                "    return total / n",
                "",
                "def long_method(a, b, c, d, e, f):",
                "    x = a + b",
                "    if x > 0:",
                "        x += c",
                "    if x > 1:",
                "        x += d",
                "    if x > 2:",
                "        x += e",
                "    if x > 3:",
                "        x += f",
                "    return x",
            ]
        ),
        encoding="utf-8",
    )

    results = run_pipeline(sample, output_dir=tmp_path / "artifacts")

    classifications = {result.final_classification for result in results}
    categories = {result.finding.category for result in results}

    assert (
        "formally_confirmed_bug" in classifications
        or "unconfirmed_hypothesis" in classifications
        or "vulnerability_potential_with_partial_evidence" in classifications
    )
    assert "smell_heuristic" in classifications
    assert "division_by_zero" in categories
    assert "out_of_bounds" in categories


def test_preprocess_ignores_test_functions_and_annotations(tmp_path: Path) -> None:
    sample = tmp_path / "sample_annotations.py"
    sample.write_text(
        "\n".join(
            [
                "from typing import List",
                "",
                "def target(xs: List[int], i: int):",
                "    return xs[i]",
                "",
                "def test_target():",
                "    data: List[int] = [1, 2, 3]",
                "    return data[0]",
            ]
        ),
        encoding="utf-8",
    )

    results = run_pipeline(sample, output_dir=tmp_path / "artifacts")

    unit_names = {result.unit_name for result in results}
    expressions = {result.finding.metadata.get("expression") for result in results if result.finding.metadata}

    assert "test_target" not in unit_names
    assert "List[int]" not in expressions
