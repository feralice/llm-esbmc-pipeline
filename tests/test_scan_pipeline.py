import json
import sys
from pathlib import Path

import pytest

import main
from research_pipeline.llm.prompt_variants import apply_variants
from research_pipeline.llm.prompts import load_system_prompt
from research_pipeline.models import Finding
from research_pipeline.scan.pipeline import DEFAULT_VARIANTS, execute_scan, plan_scan

REPO = {
    "calc.py": "def ratio(a, b):\n    return a / b\n\n"
               "def first(xs):\n    return xs[0]\n\n"
               "def label(x):\n    return str(x)\n",
    "app.py": "from calc import ratio, first\n\n"
              "def mean(xs):\n    if not xs:\n        return 0\n    return ratio(sum(xs), len(xs))\n\n"
              "def head(xs):\n    return first(xs) + ratio(1, 2)\n",
}


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    for name, text in REPO.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _finding(expression: str, verifiable: bool = True) -> Finding:
    return Finding(id="f", stage="llm_analysis", finding_type="suspected_bug", category="", title="",
                   explanation="may crash", evidence=[], verifiable=verifiable, confidence="high",
                   metadata={"expression": expression, "violated_property": "ZeroDivisionError"})


class _Analyzer:
    model = "fake-model"

    def __init__(self, fail_on: str = ""):
        self.units = []
        self.fail_on = fail_on
        self.telemetry_events = []

    def analyze(self, unit):
        self.units.append(unit)
        self.telemetry_events.append({"total_tokens": 10})
        if unit.qualname == self.fail_on:
            raise RuntimeError("usage limit")
        if unit.qualname == "ratio":
            return [_finding("a / b"), _finding("a / b"), _finding("b", verifiable=False)]
        return []


def _fake_verify(calls: list):
    def verify(hypotheses, *, llm, output_dir, completed, on_result, **kwargs):
        calls.append({"hypotheses": hypotheses, "llm": llm, "completed": completed, "kwargs": kwargs})
        results = []
        for index, h in enumerate(hypotheses):
            data = completed.get(index) or {
                "hypothesis": h.to_dict(), "verdict": "CONFIRMED", "reason": "", "attempts": [], "llm_calls": 1,
                "program_path": "p.py", "tokens": 5, "replay": {"exception_type": "ZeroDivisionError",
                                                                 "inputs": [1, 0]}}
            on_result(index, data)
            results.append(data)
        return results
    return verify


def test_plan_ranks_risky_and_called_functions_first_and_writes_the_selection(tmp_path: Path) -> None:
    out = tmp_path / "out"
    plan = plan_scan(_repo(tmp_path), out)
    assert [t.qualname for t in plan.targets] == ["ratio", "first", "mean", "head", "label"]
    assert plan.targets[0].callers == 2 and plan.targets[-1].risky_operations == 0
    selection = json.loads((out / "scan_selection.json").read_text(encoding="utf-8"))
    assert selection["selected"] == 5 and selection["estimated_detection_tokens"] == plan.estimated_tokens > 0
    assert json.loads((out / "scan_graph.json").read_text(encoding="utf-8"))["stats"]["resolved_calls"] == 3


def test_plan_limit_keeps_the_top_of_the_ranking_and_counts_the_rest(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out", limit=2)
    assert [t.qualname for t in plan.targets] == ["ratio", "first"] and plan.candidates_total == 5
    assert plan.estimated_tokens < plan_scan(_repo(tmp_path), tmp_path / "o2").estimated_tokens


def test_scan_prompt_is_a5_plus_the_caller_section() -> None:
    assert DEFAULT_VARIANTS == ("A1", "A2", "A12")
    prompt = load_system_prompt(include_smells=False, v2_detection=True, v2_variants=DEFAULT_VARIANTS)
    assert prompt == apply_variants(load_system_prompt(include_smells=False, v2_detection=True), DEFAULT_VARIANTS)
    assert "## CHAMADAS NO REPOSITÓRIO" in prompt and "## PARTIÇÃO DE ENTRADAS" in prompt


def test_execute_sends_caller_context_and_only_verifiable_findings_to_verify(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    analyzer, calls = _Analyzer(), []
    report = execute_scan(plan, analyzer=analyzer, spec_llm="spec", verify=_fake_verify(calls), bound=7)
    ratio_unit = next(u for u in analyzer.units if u.qualname == "ratio")
    assert "if not xs:" in ratio_unit.caller_context
    assert "return target_function(sum(xs), len(xs))" in ratio_unit.caller_context
    [call] = calls
    assert [(h.function, h.suspect_expression) for h in call["hypotheses"]] == [("ratio", "a / b")]
    assert call["hypotheses"][0].file == str(plan.root / "calc.py")
    assert call["llm"] == "spec" and call["kwargs"] == {"bound": 7}
    assert report["detection"]["hypotheses"] == 1 and report["detection"]["held"] == 1
    assert report["detection"]["tokens"] == 50 and report["verification"]["by_verdict"]["CONFIRMED"] == 1
    summary = (tmp_path / "out" / "scan_summary.md").read_text(encoding="utf-8")
    assert "`calc.py` `ratio`: `a / b`; ZeroDivisionError; entrada: `[1, 0]`" in summary
    assert json.loads((tmp_path / "out" / "scan_report.json").read_text(encoding="utf-8"))["results"]


def test_resume_retries_only_failed_detections_and_keeps_verdicts(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    report = execute_scan(plan, analyzer=_Analyzer(fail_on="mean"), spec_llm=None, verify=_fake_verify([]))
    assert report["detection"]["failed"] == 1
    analyzer, calls = _Analyzer(), []
    report = execute_scan(plan, analyzer=analyzer, spec_llm=None, resume=True, verify=_fake_verify(calls))
    assert [u.qualname for u in analyzer.units] == ["mean"]
    assert report["detection"]["failed"] == 0 and 0 in calls[0]["completed"]


def test_resume_refuses_a_different_selection(tmp_path: Path) -> None:
    execute_scan(plan_scan(_repo(tmp_path), tmp_path / "out"), analyzer=_Analyzer(), spec_llm=None,
                 verify=_fake_verify([]))
    with pytest.raises(ValueError, match="cannot resume"):
        execute_scan(plan_scan(_repo(tmp_path), tmp_path / "out", limit=1), analyzer=_Analyzer(), spec_llm=None,
                     resume=True, verify=_fake_verify([]))


def _run_main(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["main.py", *argv])
    return main.main()


def test_cli_without_yes_is_a_dry_run_that_builds_no_llm(tmp_path: Path, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("an LLM was built during a dry run")
    monkeypatch.setattr(main, "build_analyzer", forbidden)
    monkeypatch.setattr(main, "LLMClient", forbidden)
    monkeypatch.setattr(main, "execute_scan", forbidden)
    out = tmp_path / "out"
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir", str(out),
                                   "--backend", "openai", "--scan-limit", "2"]) == 0
    assert json.loads((out / "scan_selection.json").read_text(encoding="utf-8"))["selected"] == 2
    assert not (out / "scan_report.json").exists()


def test_cli_with_yes_runs_detection_and_verify(tmp_path: Path, monkeypatch) -> None:
    analyzer, built = _Analyzer(), {}

    def build(**kwargs):
        built["analyzer"] = kwargs
        return analyzer

    class Client:
        def __init__(self, **kwargs):
            built["spec"] = kwargs
            self.model = kwargs["model"]

    calls = []
    monkeypatch.setattr(main, "build_analyzer", build)
    monkeypatch.setattr(main, "LLMClient", Client)
    monkeypatch.setattr("research_pipeline.scan.pipeline.run_verify", _fake_verify(calls))
    out = tmp_path / "out"
    code = _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir", str(out),
                                   "--backend", "openai", "--model", "gpt-5.5", "--yes", "--bound", "9",
                                   "--esbmc-command", "esbmc"])
    assert code == 0
    assert built["analyzer"]["v2_variants"] == DEFAULT_VARIANTS and built["analyzer"]["v2_detection"]
    assert built["spec"]["backend"] == "openai" and built["spec"]["model"] == "gpt-5.5"
    assert calls[0]["kwargs"]["bound"] == 9 and calls[0]["kwargs"]["esbmc_command"] == ["esbmc"]
    assert calls[0]["kwargs"]["spec_context"] == "callers"
    assert "calc:ratio" in calls[0]["kwargs"]["graph"].functions
    assert (out / "scan_report.json").exists()


def test_cli_rejects_more_than_one_input(tmp_path: Path, monkeypatch) -> None:
    root = _repo(tmp_path)
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(root), str(root)]) == 1
