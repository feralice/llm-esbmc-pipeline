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


@pytest.fixture(autouse=True)
def _no_focus_leaks():
    """--scan-focus sets a process-wide focus; no test may hand it to the next one."""
    from research_pipeline.llm.prompts import set_detection_focus
    yield
    set_detection_focus("")


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
    assert "## CALLS IN THE REPOSITORY" in prompt and "## INPUT PARTITION" in prompt


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


def test_select_targets_by_pagerank_keeps_risky_first(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out", rank="pagerank")
    names = [t.qualname for t in plan.targets]
    assert names[-1] == "label" and set(names[:2]) == {"ratio", "first"}
    assert plan.targets[0].centrality >= plan.targets[1].centrality
    selection = json.loads((tmp_path / "out" / "scan_selection.json").read_text(encoding="utf-8"))
    assert selection["rank"] == "pagerank" and "centrality" in selection["targets"][0]


def test_default_rank_is_unchanged(tmp_path: Path) -> None:
    assert [t.qualname for t in plan_scan(_repo(tmp_path), tmp_path / "out").targets] == \
        ["ratio", "first", "mean", "head", "label"]


def test_cli_scan_rank_reaches_the_selection(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir", str(out),
                                   "--backend", "openai", "--scan-rank", "pagerank"]) == 0
    assert json.loads((out / "scan_selection.json").read_text(encoding="utf-8"))["rank"] == "pagerank"


def test_scan_smells_sends_only_candidates_to_the_llm(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from research_pipeline.scan.pipeline import judge_smells
    root = tmp_path / "repo"
    root.mkdir()
    (root / "loja.py").write_text("class Pedido:\n    def total(self, c):\n        return c.a + c.b\n\n"
                                  "    def ok(self):\n        return self.x\n", encoding="utf-8")
    plan = plan_scan(root, tmp_path / "out", smells=True)
    asked = []

    class LLM:
        def complete(self, system, user, *, json_mode=False):
            asked.append(user)
            return SimpleNamespace(raw_response='{"feature_envy": true, "move_to": "c", "reason": "uses c"}')

    report = judge_smells(plan, LLM())
    assert len(asked) == 1 and "total" in asked[0]
    saved = json.loads((tmp_path / "out" / "scan_smells.json").read_text(encoding="utf-8"))
    assert saved["exploratory"] is True and saved["feature_envy"][0]["llm"]["move_to"] == "c" == \
        report["feature_envy"][0]["llm"]["move_to"]


def test_cli_scan_smells_dry_run_writes_the_candidates_without_an_llm(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir", str(out),
                                   "--backend", "openai", "--scan-smells"]) == 0
    saved = json.loads((out / "scan_smells.json").read_text(encoding="utf-8"))
    assert saved["exploratory"] is True and saved["architecture"] == [] and saved["feature_envy"] == []


def test_judge_smells_saves_each_answer_and_resumes_without_asking_again(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from research_pipeline.scan.pipeline import judge_smells
    root = tmp_path / "repo"
    root.mkdir()
    (root / "loja.py").write_text("class P:\n    def a(self, c):\n        return c.x + c.y\n\n"
                                  "    def b(self, d):\n        return d.x + d.y\n", encoding="utf-8")
    plan = plan_scan(root, tmp_path / "out", smells=True)
    asked = []

    class Flaky:
        def complete(self, system, user, *, json_mode=False):
            asked.append(user)
            if len(asked) == 2:
                raise KeyError("backend broke")
            return SimpleNamespace(raw_response='{"feature_envy": true, "move_to": "c", "reason": "r"}')

    report = judge_smells(plan, Flaky())
    assert "error" in report["feature_envy"][1]["llm"]
    asked.clear()
    judge_smells(plan, Flaky())
    assert len(asked) == 1  # only the entry that failed is asked again


def test_default_selection_does_not_report_a_centrality_it_never_measured(tmp_path: Path) -> None:
    plan_scan(_repo(tmp_path), tmp_path / "out")
    selection = json.loads((tmp_path / "out" / "scan_selection.json").read_text(encoding="utf-8"))
    assert selection["targets"][0]["centrality"] is None


def test_cli_scan_verify_agent_uses_the_agent_verifier(tmp_path: Path, monkeypatch) -> None:
    seen = {}

    class Client:
        def __init__(self, **kwargs):
            self.model = kwargs["model"]

    monkeypatch.setattr(main, "build_analyzer", lambda **kw: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", Client)
    monkeypatch.setattr(main, "make_agent", lambda backend, **kw: seen.setdefault("agent", (backend, kw)) and
                        ((lambda *a: "DONE"), True))
    monkeypatch.setattr(main, "execute_scan", lambda plan, **kw: seen.setdefault("scan", kw) and
                        {"detection": {"failed": 0}})
    code = _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir",
                                   str(tmp_path / "out"), "--backend", "openai", "--model", "gpt-5.5", "--yes",
                                   "--esbmc-command", "esbmc", "--scan-verify", "agent"])
    assert code == 0
    assert seen["agent"][0] == "claude" and seen["agent"][1]["graph_tool"] is True
    assert callable(seen["scan"]["verify"])


def test_focus_changes_the_scan_fingerprint(tmp_path: Path) -> None:
    from research_pipeline.scan.pipeline import _fingerprint
    a = plan_scan(_repo(tmp_path), tmp_path / "a", focus="parsing")
    b = plan_scan(_repo(tmp_path), tmp_path / "b", focus="math")
    assert _fingerprint(a, "m") != _fingerprint(b, "m")


def test_cli_scan_focus_reaches_the_selection(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir", str(out),
                                   "--backend", "openai", "--scan-focus", "only parsing"]) == 0
    assert json.loads((out / "scan_selection.json").read_text(encoding="utf-8"))["focus"] == "only parsing"


def test_execute_scan_writes_relatorio_md(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, verify=_fake_verify([]))
    text = (tmp_path / "out" / "relatorio.md").read_text(encoding="utf-8")
    assert "## Confirmados (1)" in text and "## Suspeitas do LLM que o ESBMC não verifica (1)" in text


def test_agent_results_without_tokens_report_cost_as_unmeasured(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")

    def verify(hypotheses, *, llm, output_dir, completed, on_result, **kw):
        return [{"hypothesis": h.to_dict(), "verdict": "AGENT_FAILED", "reason": "x"} for h in hypotheses]

    report = execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, verify=verify)
    assert report["verification_tokens"] is None
    assert "AGENT_FAILED" in (tmp_path / "out" / "scan_summary.md").read_text(encoding="utf-8")


def test_resume_refuses_a_different_verifier(tmp_path: Path) -> None:
    from research_pipeline.verify.agent_scan import agent_verifier
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, verify=_fake_verify([]))
    agent = agent_verifier(lambda *a: "DONE", esbmc_command=["esbmc"], bound=5, timeout_seconds=1, agent_timeout=1)
    with pytest.raises(ValueError, match="cannot resume"):
        execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, resume=True, verify=agent)


def test_failed_detection_is_reported_not_read_as_a_clean_repo(tmp_path: Path) -> None:
    class Broken(_Analyzer):
        def analyze(self, unit):
            raise RuntimeError("usage limit")

    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    execute_scan(plan, analyzer=Broken(), spec_llm=None, verify=_fake_verify([]))
    text = (tmp_path / "out" / "relatorio.md").read_text(encoding="utf-8")
    assert text.index("## A detecção falhou em 5 de 5 funções") < text.index("## Confirmados")
    assert "usage limit" in text


class _FirstToo(_Analyzer):
    def analyze(self, unit):
        found = super().analyze(unit)
        return [_finding("xs[0]")] if unit.qualname == "first" else found


def test_resume_keeps_each_verdict_with_its_hypothesis_when_a_new_one_appears(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    execute_scan(plan, analyzer=_FirstToo(fail_on="ratio"), spec_llm=None, verify=_fake_verify([]))
    calls = []
    execute_scan(plan, analyzer=_FirstToo(), spec_llm=None, resume=True, verify=_fake_verify(calls))
    [call] = calls
    assert [h.function for h in call["hypotheses"]] == ["ratio", "first"]
    assert list(call["completed"]) == [1]
    assert call["completed"][1]["hypothesis"]["function"] == "first"


def test_resume_refuses_a_checkpoint_saved_by_position(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    (tmp_path / "out" / "scan_checkpoint.json").write_text(json.dumps(
        {"fingerprint": "old", "detection": {}, "verify_results": {"0": {"verdict": "CONFIRMED"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot resume"):
        execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, resume=True, verify=_fake_verify([]))


def test_prompt_change_changes_the_scan_fingerprint(tmp_path: Path, monkeypatch) -> None:
    from research_pipeline.scan import pipeline
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    before = pipeline._fingerprint(plan, "m")
    monkeypatch.setattr(pipeline, "load_system_prompt", lambda **kw: "another prompt")
    assert pipeline._fingerprint(plan, "m") != before


def test_verify_config_changes_the_scan_fingerprint(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, verify=_fake_verify([]), bound=5)
    with pytest.raises(ValueError, match="cannot resume"):
        execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, resume=True, verify=_fake_verify([]), bound=9)


def test_verify_objects_do_not_break_a_resume(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, verify=_fake_verify([]), graph=object(), healer=object())
    execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, resume=True, verify=_fake_verify([]),
                 graph=object(), healer=object())


def _product_and_examples(tmp_path: Path) -> Path:
    root = _repo(tmp_path)
    for folder in ("examples", "docs"):
        (root / folder).mkdir()
        (root / folder / "demo.py").write_text("from calc import ratio\n\ndef demo(n):\n    return ratio(1, n)\n",
                                               encoding="utf-8")
    (root / "setup.py").write_text("def version(parts):\n    return parts[0]\n", encoding="utf-8")
    (root / "aio.py").write_text("async def fetch(xs):\n    return xs[0]\n", encoding="utf-8")
    return root


def test_selection_skips_examples_docs_setup_and_async_but_keeps_them_as_callers(tmp_path: Path) -> None:
    plan = plan_scan(_product_and_examples(tmp_path), tmp_path / "out")
    assert sorted(t.qualname for t in plan.targets) == ["first", "head", "label", "mean", "ratio"]
    assert plan.to_dict()["excluded"] == {"examples": 2, "setup": 1, "async": 1}
    ratio = next(t for t in plan.targets if t.qualname == "ratio")
    assert ratio.callers == 4


def test_selection_with_only_examples_is_empty_and_says_how_to_include(tmp_path: Path, capsys) -> None:
    root = tmp_path / "samples"
    (root / "examples").mkdir(parents=True)
    (root / "examples" / "s3.py").write_text("def size(xs):\n    return xs[0]\n", encoding="utf-8")
    plan = plan_scan(root, tmp_path / "out")
    assert plan.targets == [] and "--scan-include-examples" in capsys.readouterr().out
    assert [t.qualname for t in plan_scan(root, tmp_path / "o2", include_examples=True).targets] == ["size"]


def test_cli_scan_include_examples_reaches_the_selection(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_product_and_examples(tmp_path)), "--output-dir",
                                   str(out), "--backend", "openai", "--scan-include-examples"]) == 0
    assert json.loads((out / "scan_selection.json").read_text(encoding="utf-8"))["excluded"]["examples"] == 0


def test_scan_report_has_levels_for_the_engine_and_for_the_agent(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    report = execute_scan(plan, analyzer=_Analyzer(), spec_llm=None, verify=_fake_verify([]))
    assert report["levels"]["summary"]["by_level"] == {"esbmc_engine": 1}

    def agent(hypotheses, *, completed, on_result, **kw):
        return [{"hypothesis": h.to_dict(), "verdict": "CONFIRMED", "reason": "", "target_preserved": True}
                for h in hypotheses]
    agent.label = "agent:x"
    report = execute_scan(plan_scan(_repo(tmp_path), tmp_path / "o2"), analyzer=_Analyzer(), spec_llm=None,
                          verify=agent)
    assert report["levels"]["summary"]["by_level"] == {"esbmc_agent": 1}
    assert "esbmc_agent" in (tmp_path / "o2" / "scan_summary.md").read_text(encoding="utf-8")


def test_heal_mode_and_paths_change_the_scan_fingerprint(tmp_path: Path) -> None:
    from research_pipeline.scan.pipeline import _fingerprint
    from research_pipeline.verify.healing import build_healer
    plan = plan_scan(_repo(tmp_path), tmp_path / "out")
    error = build_healer("error", llm=None, esbmc_command=None)
    kb = build_healer("error+kb", llm=None, esbmc_command=None, cache_dir=tmp_path / "kb")
    assert _fingerprint(plan, "m", verify_config={"healer": error}) != _fingerprint(plan, "m", verify_config={"healer": kb})
    assert (_fingerprint(plan, "m", verify_config={"p": tmp_path / "a"})
            != _fingerprint(plan, "m", verify_config={"p": tmp_path / "b"}))


def test_setup_py_is_left_out_only_at_the_root(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "pkg").mkdir()
    (root / "pkg" / "setup.py").write_text("def configure(xs):\n    return xs[0]\n", encoding="utf-8")
    (root / "setup.py").write_text("def version(parts):\n    return parts[0]\n", encoding="utf-8")
    names = [t.qualname for t in plan_scan(root, tmp_path / "out").targets]
    assert "configure" in names and "version" not in names


def test_summary_lists_cpython_only_reproductions_apart_from_esbmc_confirmations() -> None:
    from research_pipeline.scan.pipeline import summary_markdown

    def result(verdict, function):
        return {"verdict": verdict, "reason": "", "replay": {"exception_type": "IndexError", "inputs": [0]},
                "hypothesis": {"file": "/r/a.py", "function": function, "suspect_expression": "x[0]"}}
    report = {"config": {"root": "/r"},
              "graph": {"functions": 1, "modules": 1, "resolved_calls": 0, "call_sites": 0},
              "detection": {"functions": 1, "failed": 0, "hypotheses": 2, "held": 0},
              "verification": {"by_verdict": {"CONFIRMED": 1, "REPRODUCED_CPYTHON": 1}},
              "levels": {"summary": {"by_level": {}}},
              "results": [result("CONFIRMED", "f"), result("REPRODUCED_CPYTHON", "g")]}
    text = summary_markdown(report)
    esbmc, cpython = text.split("## Reproduzidos só no CPython")
    assert "`f`" in esbmc and "`g`" not in esbmc and "`g`: `x[0]`; IndexError" in cpython


def test_scan_only_keeps_the_named_functions_with_their_rank_in_the_full_selection(tmp_path: Path) -> None:
    plan = plan_scan(_repo(tmp_path), tmp_path / "out", only=("head", "mean"))
    assert [(t.qualname, t.position) for t in plan.targets] == [("mean", 3), ("head", 4)]
    assert plan.candidates_total == 5
    selection = json.loads((tmp_path / "out" / "scan_selection.json").read_text(encoding="utf-8"))
    assert selection["only"] == ["head", "mean"] and selection["targets"][0]["position"] == 3


def test_scan_only_refuses_a_name_that_is_not_selectable(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing"):
        plan_scan(_repo(tmp_path), tmp_path / "out", only=("missing",))


def test_cli_scan_only_reaches_the_selection(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir", str(out),
                                   "--backend", "openai", "--scan-only", "head", "--scan-only", "ratio"]) == 0
    selection = json.loads((out / "scan_selection.json").read_text(encoding="utf-8"))
    assert [t["function"] for t in selection["targets"]] == ["ratio", "head"]


def test_cli_scan_only_with_an_unknown_name_fails_with_a_message(tmp_path: Path, monkeypatch, capsys) -> None:
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir",
                                   str(tmp_path / "out"), "--backend", "openai", "--scan-only", "nope"]) == 1
    assert "nope" in capsys.readouterr().err


def test_scan_smells_send_ruff_candidates_through_the_llm_filter(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from research_pipeline.scan.pipeline import judge_smells, smells_section

    root = tmp_path / "repo"
    root.mkdir()
    (root / "m.py").write_text("def f(a, b, c, d, e, g, h):\n    return a\n", encoding="utf-8")
    plan = plan_scan(root, tmp_path / "out", smells=True)
    [entry] = json.loads((tmp_path / "out" / "scan_smells.json").read_text(encoding="utf-8"))["tool_candidates"]
    assert entry["smell"] == "LongParameterList" and entry["rule"] == "PLR0913"

    class LLM:
        def complete(self, system, user, *, json_mode=False):
            return SimpleNamespace(raw_response=json.dumps(
                {"verdicts": [{"id": entry["id"], "smell": True, "reason": "seven parameters"}]}))

    judge_smells(plan, LLM())
    saved = json.loads((tmp_path / "out" / "scan_smells.json").read_text(encoding="utf-8"))
    assert saved["tool_candidates"][0]["llm"] == {"smell": True, "reason": "seven parameters"}
    section = smells_section(tmp_path / "out")
    assert "exploratório" in section and "LongParameterList" in section and "seven parameters" in section


def test_scan_smells_judge_the_code_seen_at_plan_time_and_count_what_was_not_kept(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from research_pipeline.scan.pipeline import judge_smells, smells_section

    root = tmp_path / "repo"
    root.mkdir()
    (root / "m.py").write_text("def f(a, b, c, d, e, g, h):\n    return a\n", encoding="utf-8")
    plan = plan_scan(root, tmp_path / "out", smells=True)
    (root / "m.py").write_text("import os\n" + (root / "m.py").read_text(encoding="utf-8"), encoding="utf-8")

    class LLM:
        def complete(self, system, user, *, json_mode=False):
            assert "def f(a, b" in user
            return SimpleNamespace(raw_response="not json")

    judge_smells(plan, LLM())
    [entry] = json.loads((tmp_path / "out" / "scan_smells.json").read_text(encoding="utf-8"))["tool_candidates"]
    assert "error" in entry["llm"]
    section = smells_section(tmp_path / "out")
    assert "1 mantidos" in section and "1 sem resposta da LLM" in section
