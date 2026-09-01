from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_pipeline import evaluator
from research_pipeline.evaluator import (
    EvalCounts,
    formal_confirmation_rate_defined,
    mcc_defined,
    noise_reduction_rate_defined,
    prf_defined,
)
from research_pipeline.pipeline import run_pipeline_llm_only
from research_pipeline.verification import esbmc_runner


def test_esbmc_command_applies_configured_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(x):\n    return x\n", encoding="utf-8")
    captured: list[str] = []

    monkeypatch.setattr(esbmc_runner.shutil, "which", lambda _name: "/usr/bin/esbmc")

    def fake_run(command, **_kwargs):
        captured.extend(command)
        return SimpleNamespace(
            stdout="Generated 1 VCC(s)\nVERIFICATION SUCCESSFUL\n",
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(esbmc_runner.subprocess, "run", fake_run)
    esbmc_runner.run_esbmc_on_function(
        source, "f", "finding-1", "division_by_zero", bound=7,
        output_dir=tmp_path / "artifacts",
    )

    assert captured[captured.index("--max-k-step") + 1] == "7"


@pytest.mark.parametrize("bound", [0, -1, True])
def test_invalid_bound_fails_before_esbmc(bound) -> None:
    with pytest.raises(ValueError, match="bound"):
        esbmc_runner.run_esbmc_on_function(
            "unused.py", "f", "finding-1", "division_by_zero", bound=bound
        )


def test_undefined_metrics_are_explicit() -> None:
    counts = EvalCounts()
    assert prf_defined(0, 0, 0) == {
        "precision": None,
        "recall": None,
        "f1": None,
    }
    assert mcc_defined(0, 0, 0, 0) is None
    assert formal_confirmation_rate_defined(counts) is None
    assert noise_reduction_rate_defined(counts) is None


def test_llm_run_records_partial_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(x):\n    return x\n", encoding="utf-8")

    class FailingAnalyzer:
        def analyze(self, _unit):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "research_pipeline.pipeline.build_analyzer", lambda **_kwargs: FailingAnalyzer()
    )
    output = tmp_path / "out"
    run_pipeline_llm_only([source], output_dir=output)
    status = json.loads((output / "run_status.json").read_text(encoding="utf-8"))

    assert status["status"] == "partial"
    assert status["planned_units"] == 1
    assert status["processed_units"] == 0
    assert status["failed_units"] == 1


def test_resume_skips_completed_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(x):\n    return x\n", encoding="utf-8")

    class CountingAnalyzer:
        calls = 0

        def analyze(self, _unit):
            self.calls += 1
            return []

    analyzer = CountingAnalyzer()
    monkeypatch.setattr(
        "research_pipeline.pipeline.build_analyzer", lambda **_kwargs: analyzer
    )
    output = tmp_path / "out"
    run_pipeline_llm_only([source], output_dir=output)
    run_pipeline_llm_only([source], output_dir=output, resume=True)

    assert analyzer.calls == 1


def test_resume_rejects_changed_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(x):\n    return x\n", encoding="utf-8")

    class EmptyAnalyzer:
        def analyze(self, _unit):
            return []

    monkeypatch.setattr(
        "research_pipeline.pipeline.build_analyzer", lambda **_kwargs: EmptyAnalyzer()
    )
    output = tmp_path / "out"
    run_pipeline_llm_only([source], output_dir=output, llm_model="model-a")

    with pytest.raises(ValueError, match="Não é seguro retomar"):
        run_pipeline_llm_only(
            [source], output_dir=output, llm_model="model-b", resume=True
        )


def test_benchmark_failed_cases_remain_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(x):\n    return x\n", encoding="utf-8")
    monkeypatch.setattr(evaluator, "load_ground_truth_cases", lambda _path: [(source, [])])
    monkeypatch.setattr(evaluator, "build_analyzer", lambda **_kwargs: object())
    monkeypatch.setattr(
        evaluator,
        "evaluate_file",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    counts, cis = evaluator.evaluate_model(
        ground_truth_path=tmp_path,
        backend="openai",
        model="test",
        n_bootstrap=20,
    )

    assert counts.cases_planned == 1
    assert counts.cases_evaluated == 0
    assert counts.cases_failed == 1
    assert counts.failed_cases[0]["file"] == str(source)
    assert cis == {}


def test_benchmark_resume_reuses_completed_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(x):\n    return x\n", encoding="utf-8")
    monkeypatch.setattr(evaluator, "load_ground_truth_cases", lambda _path: [(source, [])])
    monkeypatch.setattr(evaluator, "build_analyzer", lambda **_kwargs: object())
    calls = 0

    def fake_evaluate_file(**_kwargs):
        nonlocal calls
        calls += 1
        return EvalCounts(bug_func_tn=1)

    monkeypatch.setattr(evaluator, "evaluate_file", fake_evaluate_file)
    output = tmp_path / "per_file"
    first, _ = evaluator.evaluate_model(
        ground_truth_path=tmp_path,
        backend="openai",
        model="test",
        output_dir=output,
        n_bootstrap=0,
    )
    second, _ = evaluator.evaluate_model(
        ground_truth_path=tmp_path,
        backend="openai",
        model="test",
        output_dir=output,
        n_bootstrap=0,
        resume=True,
    )

    assert calls == 1
    assert first.bug_func_tn == second.bug_func_tn == 1
    assert second.cases_evaluated == 1
