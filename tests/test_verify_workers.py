import threading
import time
from pathlib import Path

import pytest

from research_pipeline.llm.rate_limit import UsageLimitReached
from research_pipeline.verify import loop
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.outcome import CONFIRMED


def _hypotheses(tmp_path: Path, n: int) -> list[BugHypothesis]:
    source = tmp_path / "mod.py"
    source.write_text("def f(a):\n    return 1 // a\n", encoding="utf-8")
    return [BugHypothesis(str(source), "f", f"1 // a{i}", category="division_by_zero") for i in range(n)]


def _fake_verify(monkeypatch, delays, *, fail_at=None):
    started = []
    lock = threading.Lock()

    def fake(h, **kwargs):
        index = int(h.suspect_expression.rsplit("a", 1)[1])
        with lock:
            started.append(index)
        time.sleep(delays[index % len(delays)])
        if index == fail_at:
            raise UsageLimitReached("limit")
        return loop.VerifyResult(h, CONFIRMED, f"done {index}")

    monkeypatch.setattr(loop, "verify_hypothesis", fake)
    return started


def _run(hypotheses, tmp_path, **kwargs):
    return loop.run_verify(hypotheses, llm=None, output_dir=tmp_path / "out", **kwargs)


def test_parallel_results_keep_the_input_order(tmp_path, monkeypatch):
    _fake_verify(monkeypatch, delays=[0.05, 0.0, 0.03, 0.0, 0.01])
    results = _run(_hypotheses(tmp_path, 5), tmp_path, workers=4)
    assert [r["reason"] for r in results] == [f"done {i}" for i in range(5)]


def test_one_worker_and_many_workers_give_the_same_results(tmp_path, monkeypatch):
    _fake_verify(monkeypatch, delays=[0.02, 0.0, 0.01])
    hypotheses = _hypotheses(tmp_path, 6)
    sequential = _run(hypotheses, tmp_path, workers=1)
    parallel = _run(hypotheses, tmp_path, workers=3)
    assert sequential == parallel


def test_on_result_is_called_once_per_hypothesis(tmp_path, monkeypatch):
    _fake_verify(monkeypatch, delays=[0.0])
    seen = []
    _run(_hypotheses(tmp_path, 5), tmp_path, workers=3, on_result=lambda index, data: seen.append(index))
    assert sorted(seen) == [0, 1, 2, 3, 4]


def test_a_usage_limit_stops_the_batch_without_starting_the_rest(tmp_path, monkeypatch):
    started = _fake_verify(monkeypatch, delays=[0.2], fail_at=0)
    with pytest.raises(UsageLimitReached):
        _run(_hypotheses(tmp_path, 8), tmp_path, workers=2)
    assert len(started) < 8


def test_default_is_sequential_and_unchanged(tmp_path, monkeypatch):
    started = _fake_verify(monkeypatch, delays=[0.0])
    results = _run(_hypotheses(tmp_path, 3), tmp_path)
    assert started == [0, 1, 2] and len(results) == 3
