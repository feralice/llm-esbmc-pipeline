from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import smells_metricas


def _row(i: str, smell: str, label: int, experience: bool, statistics: bool) -> dict:
    return {"id": i, "smell": smell, "label": label, "path": "a.py", "line": 1, "metrics": {}, "snippet": "x",
            "tool_experience_based": experience, "tool_statistics_based": statistics}


def test_tool_only_counts_positives_the_tool_never_reported_as_misses() -> None:
    rows = [_row("1", "LongMethod", 1, True, False), _row("2", "LongMethod", 0, True, False),
            _row("3", "LongMethod", 1, False, False), _row("4", "LargeClass", 1, False, True)]
    result = smells_metricas.tool_only(rows)
    assert result["tool"]["tp"] == 2 and result["tool"]["fp"] == 1 and result["tool"]["fn"] == 1
    assert result["per_smell"]["LongMethod"]["tool"]["fn"] == 1


def test_table_shows_positives_next_to_precision_and_recall() -> None:
    rows = [_row("1", "LongMethod", 1, True, False), _row("2", "LongMethod", 0, True, False)]
    table = smells_metricas.table(smells_metricas.tool_only(rows), rows)
    assert "LongMethod" in table and "| 1 |" in table
