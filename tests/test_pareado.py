from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import pareado


def test_mcnemar_exact_matches_known_values() -> None:
    assert pareado.mcnemar_exact(5, 0) == 0.0625
    assert pareado.mcnemar_exact(6, 0) == 0.03125
    assert pareado.mcnemar_exact(3, 3) == 1.0
    assert pareado.mcnemar_exact(0, 0) == 1.0


def test_discordant_counts_only_bugs_that_change_side() -> None:
    a = {"b1": True, "b2": True, "b3": False, "b4": False}
    b = {"b1": True, "b2": False, "b3": True, "b4": False}
    assert pareado.discordant(a, b) == (1, 1)


def test_bootstrap_interval_is_reproducible_and_brackets_difference() -> None:
    a = {f"b{i}": i < 30 for i in range(47)}
    b = {f"b{i}": i < 20 for i in range(47)}
    low, high = pareado.bootstrap_difference(a, b, seed=1)
    assert (low, high) == pareado.bootstrap_difference(a, b, seed=1)
    assert low <= 10 <= high and low > 0


def test_summary_row_reads_cost_and_acceptance_from_telemetry() -> None:
    report = {"telemetry": {"detection": {"calls": 2, "prompt_tokens": 100, "tokens": 120, "cost_usd": 1.5, "seconds": 3, "calls_with_cache_data": 2},
                            "synthesis": {"calls": 4, "prompt_tokens": 400, "tokens": 450, "cost_usd": 2.5, "seconds": 7, "calls_with_cache_data": 4}},
              "results": [{"verdict": "CONFIRMED"}, {"verdict": "UNSUPPORTED"}]}
    row = pareado.cost_row(report)
    assert row["calls"] == 6 and row["prompt_tokens"] == 500 and row["cost_usd"] == 4.0 and row["seconds"] == 10


def test_cost_row_marks_tokens_and_cost_unknown_when_cache_data_is_missing() -> None:
    report = {"telemetry": {"detection": {"calls": 2, "prompt_tokens": 146, "tokens": 900, "cost_usd": 0.0,
                                          "seconds": 3, "calls_with_cache_data": 0}}, "results": []}
    row = pareado.cost_row(report)
    assert row["calls"] == 2 and row["prompt_tokens"] is None and row["cost_usd"] is None
