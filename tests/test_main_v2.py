from __future__ import annotations

import json
from pathlib import Path

import pytest

import main
from research_pipeline.models import Finding
from research_pipeline.verify.capabilities import all_rules_report
from research_pipeline.verify.rules import ALL_RULES


class _Analyzer:
    calls = 0

    def analyze(self, unit):
        type(self).calls += 1
        return [
            Finding(
                id="f1",
                stage="llm_analysis",
                finding_type="suspected_bug",
                category="division_by_zero",
                title="",
                explanation="denominator may be zero",
                evidence=[],
                verifiable=True,
                confidence="high",
                metadata={"expression": "x // y"},
            )
        ]


class _Synthesizer:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]


class _AnalyzerWithSmell:
    def analyze(self, unit):
        return [
            Finding(
                id="smell",
                stage="llm_analysis",
                finding_type="smell_heuristic",
                category="long_method",
                title="",
                explanation="too long",
                evidence=[],
                verifiable=False,
                confidence="high",
                metadata={},
            ),
            Finding(
                id="wrong-result-bug",
                stage="llm_analysis",
                finding_type="suspected_bug",
                category="",
                title="",
                explanation="returns the wrong value, nothing raises",
                evidence=[],
                verifiable=False,
                confidence="high",
                metadata={"expression": "f(...)"},
            ),
        ]


def test_v2_forwards_only_findings_the_llm_marks_verifiable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(value: int) -> int:\n    return value\n", encoding="utf-8")
    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _AnalyzerWithSmell())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", lambda hypotheses, **kwargs: captured.setdefault("candidates", hypotheses) or [])

    args = main.build_parser().parse_args(["--mode", "hybrid", "--input", str(source), "--output-dir", str(tmp_path / "out")])

    assert main.mode_v2(args) == 0
    assert captured["candidates"] == []


def test_v2_detects_before_synthesizing(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    captured = {}

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)

    def fake_pipeline(candidates, **kwargs):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr(main, "run_verify", fake_pipeline)
    args = main.build_parser().parse_args(
        [
            "--mode", "hybrid", "--input", str(source),
            "--output-dir", str(tmp_path / "out"),
        ]
    )

    assert main.mode_v2(args) == 0
    assert len(captured["candidates"]) == 1
    candidate = captured["candidates"][0]
    assert candidate.function == "divide"
    assert candidate.category == ""  # V2 detection gives no category
    assert candidate.suspect_expression == "x // y"


def test_v2_resume_does_not_repeat_completed_detection(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    _Analyzer.calls = 0
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", lambda hypotheses, **kwargs: [])
    parser = main.build_parser()
    base = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(output)]

    assert main.mode_v2(parser.parse_args(base)) == 0
    assert _Analyzer.calls == 1
    assert main.mode_v2(parser.parse_args([*base, "--resume"])) == 0
    assert _Analyzer.calls == 1


def test_v2_marks_checkpoint_interrupted_when_synthesis_is_cancelled(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)

    def interrupted_pipeline(candidates, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "run_verify", interrupted_pipeline)
    args = main.build_parser().parse_args(
        ["--mode", "hybrid", "--input", str(source), "--output-dir", str(output)]
    )

    assert main.mode_v2(args) == 2
    checkpoint = json.loads((output / "v2_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "interrupted"
    assert "interrupted_at" in checkpoint


def test_v2_end_to_end_excludes_patch_context_items_from_detection(
    tmp_path: Path, monkeypatch
) -> None:
    detection_dir = tmp_path / "detection"
    detection_dir.mkdir()
    (detection_dir / "a.py").write_text(
        "def divide(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    (detection_dir / "b.py").write_text(
        "def divide2(x: int, y: int) -> int:\n    return x // y\n",
        encoding="utf-8",
    )
    manifest = {
        "evaluation_policy": {"patch_context_items": ["b"]},
        "items": [
            {"id": "a", "detection_file": "detection/a.py", "categories": ["division_by_zero"], "function": "divide"},
            {"id": "b", "detection_file": "detection/b.py", "categories": ["division_by_zero"], "function": "divide2"},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": [{"id": "a"}, {"id": "b"}]}), encoding="utf-8")

    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)

    def fake_pipeline(candidates, **kwargs):
        captured["candidates"] = candidates
        return []

    monkeypatch.setattr(main, "run_verify", fake_pipeline)

    args = main.build_parser().parse_args(
        [
            "--mode", "hybrid",
            "--input", str(detection_dir),
            "--ground-truth", str(ground_truth),
            "--output-dir", str(tmp_path / "out"),
        ]
    )

    assert main.mode_v2(args) == 0
    analyzed_files = {c.file for c in captured["candidates"]}
    assert analyzed_files == {str(detection_dir / "a.py")}


def test_summarize_v2_telemetry_reports_cache_hit_rate_per_stage():
    events = [
        {"stage": "detection", "status": "success", "duration_seconds": 1.0,
         "total_tokens": 100, "prompt_tokens": 80, "cached_tokens": 64},
        {"stage": "detection", "status": "success", "duration_seconds": 1.0,
         "total_tokens": 100, "prompt_tokens": 80, "cached_tokens": 0},
        {"stage": "synthesis", "status": "success", "duration_seconds": 1.0,
         "total_tokens": 100, "prompt_tokens": 80},  # e.g. codex backend: no cache field
    ]
    summary = main._summarize_v2_telemetry(events)
    assert summary["detection"]["calls_with_cache_data"] == 2
    assert summary["detection"]["cached_tokens"] == 64
    assert summary["detection"]["cache_hit_rate"] == 0.4
    assert summary["synthesis"]["calls_with_cache_data"] == 0
    assert summary["synthesis"]["cache_hit_rate"] is None


def test_summarize_detection_trace_keeps_failures_distinct():
    summary = main._summarize_detection_trace([
        {
            "function": "f",
            "located_candidates": 2,
            "classified_candidates": 1,
            "rejected_candidates": 1,
        },
        {
            "function": "g",
            "failure_stage": "classify",
            "error": "invalid JSON",
        },
    ])

    assert summary == {
        "units": 2,
        "located_candidates": 2,
        "classified_candidates": 1,
        "rejected_candidates": 1,
        "localization_failures": 0,
        "classification_failures": 1,
    }




def test_resume_retries_pipeline_errors_and_keeps_real_verdicts() -> None:
    checkpoint = {"verify_results": {"0": {"verdict": "CONFIRMED"}, "1": {"verdict": "PIPELINE_ERROR"},
                                     "2": {"verdict": "UNSUPPORTED"}}}

    assert sorted(main._resumable_results(checkpoint)) == [0, 2]


def test_detection_stage_stops_before_verification(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", lambda *a, **k: pytest.fail("verification must not run"))
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
                                           "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    report = json.loads((out / "v2_verify_report.json").read_text())
    assert report["coverage"] == {"status": "complete", "stage": "detection"}
    assert len(report["detection"]["candidates"]) == 1 and report["results"] == []


def test_detection_stage_skips_patch_context_items_like_end_to_end(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "det").mkdir()
    for name in ("kept", "patch_only"):
        (tmp_path / "det" / f"{name}.py").write_text("def divide(x: int, y: int) -> int:\n    return x // y\n")
    items = [{"id": name, "detection_file": f"det/{name}.py", "function": "divide", "categories": ["x"]}
             for name in ("kept", "patch_only")]
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"evaluation_policy": {"patch_context_items": ["patch_only"]}, "items": items}))
    (tmp_path / "ground_truths.json").write_text(json.dumps({"items": items}))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input",
                                           str(tmp_path / "det"), "--ground-truth",
                                           str(tmp_path / "ground_truths.json"), "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    files = json.loads((out / "v2_verify_report.json").read_text())["config"]["input_files"]
    assert [Path(f).name for f in files] == ["kept.py"]


def test_variants_enter_the_run_config(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    seen = {}
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: seen.update(kwargs) or _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--v2-variants", "A1,A2",
                                           "--input", str(source), "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    assert seen["v2_variants"] == ("A1", "A2")
    assert json.loads((out / "v2_verify_report.json").read_text())["config"]["v2_variants"] == ["A1", "A2"]


def test_v2_verify_gets_the_probed_rules_and_a_resume_reuses_them(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    report = {"reason": "sondas", "key": "k", "identity": {}, "active_rules": ["none_guards_attribute"],
              "disabled_rules": ["compat_percent_format"], "results": {}}
    calls, seen = [], {}

    def fake_resolve(esbmc_command, **kwargs):
        calls.append(kwargs)
        return report

    def fake_verify(hypotheses, **kwargs):
        seen["rules"] = kwargs["rules"]
        return []

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "resolve_rules", fake_resolve)
    monkeypatch.setattr(main, "run_verify", fake_verify)
    out = tmp_path / "out"
    base = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(out)]

    assert main.mode_v2(main.build_parser().parse_args(base)) == 0
    # Only what the probes switched off goes off; a rule id the report does not know stays on.
    assert seen["rules"] == ALL_RULES - {"compat_percent_format"}
    assert calls[0]["enabled"] is True and calls[0]["resumed"] is False
    assert json.loads((out / "v2_verify_report.json").read_text())["config"]["capabilities"] == report
    assert json.loads((out / "v2_checkpoint.json").read_text())["capabilities"] == report
    seen.clear()
    assert main.mode_v2(main.build_parser().parse_args([*base, "--resume"])) == 0
    assert len(calls) == 1 and seen["rules"] == ALL_RULES - {"compat_percent_format"}


def test_probes_use_the_command_verification_runs_and_the_run_bound(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    calls = []

    def fake_resolve(esbmc_command, **kwargs):
        calls.append((esbmc_command, kwargs))
        return all_rules_report("teste")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "_VERIFY_DEFAULT_ESBMC", str(tmp_path / "no-esbmc"))
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "resolve_rules", fake_resolve)
    monkeypatch.setattr(main, "run_verify", lambda hypotheses, **kwargs: [])
    base = ["--mode", "hybrid", "--input", str(source), "--bound", "7", "--timeout", "300"]

    assert main.mode_v2(main.build_parser().parse_args([*base, "--output-dir", str(tmp_path / "a")])) == 0
    command, kwargs = calls[-1]
    # Without --esbmc-command, verification's check() runs `esbmc` from PATH; the probes must too.
    assert command == ["esbmc"] and kwargs["bound"] == 7 and kwargs["timeout_seconds"] == 60
    assert main.mode_v2(main.build_parser().parse_args(
        [*base, "--timeout", "20", "--esbmc-command", "my-esbmc", "--output-dir", str(tmp_path / "b")])) == 0
    command, kwargs = calls[-1]
    assert command == ["my-esbmc"] and kwargs["timeout_seconds"] == 20


def test_a_resumed_checkpoint_with_results_and_no_rule_set_keeps_every_rule(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    calls, seen = [], {}

    def fake_resolve(esbmc_command, **kwargs):
        calls.append(kwargs)
        return all_rules_report("teste")

    def fake_verify(hypotheses, **kwargs):
        seen["rules"] = kwargs["rules"]
        return []

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "resolve_rules", fake_resolve)
    monkeypatch.setattr(main, "run_verify", fake_verify)
    out = tmp_path / "out"
    base = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(out)]
    assert main.mode_v2(main.build_parser().parse_args(base)) == 0
    checkpoint_path = out / "v2_checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    del checkpoint["capabilities"]
    checkpoint["verify_results"] = {"0": {"verdict": "NOT_CONFIRMED"}}
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    seen.clear()

    assert main.mode_v2(main.build_parser().parse_args([*base, "--resume"])) == 0
    assert calls[-1]["resumed"] is True and seen["rules"] == ALL_RULES


def test_no_capability_probes_flag_reaches_resolve_rules() -> None:
    args = main.build_parser().parse_args(["--mode", "hybrid", "--input", "x.py", "--no-capability-probes",
                                           "--capability-cache", "cache"])
    assert args.capability_probes is False and args.capability_cache == "cache"
    assert main.build_parser().parse_args(["--mode", "hybrid", "--input", "x.py"]).capability_probes is True


def _pool(tmp_path: Path) -> Path:
    sources = tmp_path / "pool" / "funcao_com_bug"
    sources.mkdir(parents=True)
    (sources / "x_1.py").write_text("def pick(values, i):\n    return values[i + 1]\n", encoding="utf-8")
    ground_truth = tmp_path / "pool" / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": [
        {"id": "x_1", "file": "x_1.py", "function": "pick", "expression": "values[i + 1]",
         "failure_kind": "excecao_local", "provenance": {"project": "outro"}}]}), encoding="utf-8")
    return ground_truth


def _detection_args(source: Path, out: Path, *extra: str):
    return main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
                                           "--output-dir", str(out), *extra])


def test_a13_loads_the_example_pool_and_records_it(tmp_path: Path, monkeypatch) -> None:
    from research_pipeline.llm.prompts import set_example_pool

    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    ground_truth = _pool(tmp_path)
    out = tmp_path / "out"
    args = _detection_args(source, out, "--v2-variants", "A1,A2,A13", "--example-pool", str(ground_truth))
    try:
        assert main.mode_v2(args) == 0
    finally:
        set_example_pool(None)
    config = json.loads((out / "v2_verify_report.json").read_text())["config"]
    assert config["example_pool"] == str(ground_truth.resolve()) and config["example_k"] == 3
    fingerprint = json.loads((out / "v2_checkpoint.json").read_text())["fingerprint"]
    assert "example_pool" in fingerprint and "detector_system_prompt" in fingerprint


def test_a13_with_a_missing_pool_exits_with_error(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    args = _detection_args(source, tmp_path / "out", "--v2-variants", "A13",
                           "--example-pool", str(tmp_path / "nao_existe.json"))
    assert main.mode_v2(args) == 1


def test_fingerprint_keeps_its_keys_for_earlier_variants() -> None:
    keys = set(main._v2_fingerprint({"v2_variants": ["A1", "A2"]}, []))
    assert keys == {"config", "sources", "detector_prompt", "detector_schema", "spec_prompt"}
    assert "detector_system_prompt" in main._v2_fingerprint({"v2_variants": ["A1", "A2", "A14"]}, [])
