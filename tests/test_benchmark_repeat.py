"""Tests for `--repeat` wiring in `mode_benchmark_v1`.

No LLM call is made: `evaluate_model` is monkeypatched to return canned
EvalCounts per call, so these test only the CLI wiring (call count, raw-run
persistence, --resume rejection) -- never the stochastic behaviour itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import main
from research_pipeline.evaluator import EvalCounts


def _args(tmp_path: Path, **overrides) -> "main.argparse.Namespace":
    argv = [
        "--mode", "benchmark-v1",
        "--input", str(tmp_path),
        "--backend", "openai",
    ]
    args = main.build_parser().parse_args(argv)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_repeat_one_calls_evaluate_model_once(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_evaluate_model(**kwargs):
        calls["n"] += 1
        return EvalCounts(bug_tp=1), {}

    monkeypatch.setattr(main, "evaluate_model", fake_evaluate_model)
    args = _args(tmp_path, repeat=1)
    assert main.mode_benchmark_v1(args) == 0
    assert calls["n"] == 1


def test_repeat_n_calls_evaluate_model_n_times_and_persists_raw_runs(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_evaluate_model(**kwargs):
        calls["n"] += 1
        # vary the outcome per call so the summary isn't trivially constant
        return EvalCounts(bug_tp=calls["n"], bug_fp=0, bug_fn=0), {}

    monkeypatch.setattr(main, "evaluate_model", fake_evaluate_model)
    report_path = tmp_path / "benchmark_x.json"
    args = _args(tmp_path, repeat=3, report=str(report_path))
    assert main.mode_benchmark_v1(args) == 0
    assert calls["n"] == 3

    raw_runs_path = tmp_path / "raw_runs_benchmark_x.json"
    assert raw_runs_path.exists()
    persisted = json.loads(raw_runs_path.read_text(encoding="utf-8"))
    assert len(persisted["raw_runs"]) == 3
    assert persisted["aggregate"]["bug_precision"]["n_runs"] == 3


def test_repeat_greater_than_one_rejects_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(
        main, "evaluate_model",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    args = _args(tmp_path, repeat=3, resume=True, report=str(tmp_path / "b.json"))
    assert main.mode_benchmark_v1(args) == 1
