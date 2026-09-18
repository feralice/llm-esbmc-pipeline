"""Tests for `run_repeated` / `summarize_repeated_runs`.

The LLM is stochastic; a single benchmark run measures nothing about
variance. These helpers let a caller run the same evaluation N times and
report mean/stdev alongside the raw per-run outcomes, without discarding
the raw values the way a bare average would.
"""

from __future__ import annotations

import pytest

from research_pipeline.evaluator import EvalCounts, run_repeated, summarize_repeated_runs


def _counts(bug_tp: int, bug_fp: int, bug_fn: int) -> EvalCounts:
    return EvalCounts(bug_tp=bug_tp, bug_fp=bug_fp, bug_fn=bug_fn)


def test_run_repeated_calls_run_once_exactly_n_times():
    calls = []

    def run_once() -> EvalCounts:
        calls.append(1)
        return _counts(1, 0, 0)

    results = run_repeated(run_once, n_runs=5)
    assert len(calls) == 5
    assert len(results) == 5


def test_run_repeated_rejects_zero_or_negative_n():
    with pytest.raises(ValueError):
        run_repeated(lambda: _counts(0, 0, 0), n_runs=0)


def test_summarize_computes_mean_and_stdev_across_varying_runs():
    # Run 1: perfect precision. Run 2: one false positive drags it down.
    runs = [_counts(2, 0, 0), _counts(2, 1, 0)]
    summary = summarize_repeated_runs(runs)
    bug_precision = summary["aggregate"]["bug_precision"]
    assert bug_precision["n_runs"] == 2
    assert bug_precision["n_defined"] == 2
    assert bug_precision["mean"] == pytest.approx((1.0 + 2 / 3) / 2)
    assert bug_precision["stdev"] > 0


def test_summarize_preserves_raw_per_run_outcomes():
    runs = [_counts(1, 0, 0), _counts(0, 1, 0)]
    summary = summarize_repeated_runs(runs)
    assert len(summary["raw_runs"]) == 2
    assert summary["raw_runs"][0]["bug_precision"] == 1.0
    assert summary["raw_runs"][1]["bug_precision"] == 0.0


def test_summarize_metric_undefined_in_every_run_aggregates_to_none_not_zero():
    # No bugs attempted in either run -- precision is undefined, not 0.
    runs = [_counts(0, 0, 0), _counts(0, 0, 0)]
    summary = summarize_repeated_runs(runs)
    bug_precision = summary["aggregate"]["bug_precision"]
    assert bug_precision["mean"] is None
    assert bug_precision["n_defined"] == 0
    assert bug_precision["n_runs"] == 2


def test_summarize_single_defined_value_has_zero_stdev_not_an_exception():
    runs = [_counts(1, 0, 0)]
    summary = summarize_repeated_runs(runs)
    assert summary["aggregate"]["bug_precision"]["stdev"] == 0.0


def test_summarize_rejects_empty_run_list():
    with pytest.raises(ValueError):
        summarize_repeated_runs([])
