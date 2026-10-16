import importlib.util
from pathlib import Path

from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.orchestrator import orchestrate
from research_pipeline.verify.report import evaluate_verify
from research_pipeline.verify.routing import route

_SPEC = importlib.util.spec_from_file_location(
    "v2_orchestrate", Path(__file__).resolve().parents[1] / "scripts" / "v2_orchestrate.py")
v2_orchestrate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v2_orchestrate)

GT = {"a": {"function": "f", "expression": "x[i]", "crash_expressions": []}}


def _result(hid, expression, verdict="VALUE_CONFIRMED", oracle="value"):
    return {"verdict": verdict, "reason": "", "hypothesis": {
        "hypothesis_id": hid, "file": "d/a.py", "function": "f", "suspect_expression": expression, "oracle": oracle}}


def test_value_hypotheses_get_no_arm_whatever_stopped_them():
    assert route(_result("1", "x[i]", verdict="ESBMC_TIMEOUT")) == ()
    assert route(_result("1", "x[i]", verdict="ESBMC_TIMEOUT", oracle="")) != ()


def test_the_orchestrator_keeps_the_engine_value_verdict():
    calls = []
    rows = orchestrate([_result("1", "x[i]")], arms={"dynamic": lambda r: calls.append(r) or {"verdict": "FUZZ_FOUND"}},
                       state={}, save=lambda: None)
    assert calls == [] and rows[0]["final"] == "VALUE_CONFIRMED"


def test_value_confirmations_count_apart_and_only_at_the_bug_line():
    results = [_result("1", "x[i]"), _result("2", "y"), _result("3", "x[i]"), _result("4", "x[i]", oracle="")]
    rows = [{"hypothesis_id": "1", "final": "VALUE_CONFIRMED", "steps": []},
            {"hypothesis_id": "2", "final": "VALUE_CONFIRMED", "steps": []},
            {"hypothesis_id": "3", "final": "VALUE_VIOLATION", "steps": []},
            {"hypothesis_id": "4", "final": "CONFIRMED", "steps": []}]
    summary = v2_orchestrate.summarize(rows, results, GT)
    assert summary["value_confirmed_at_bug"] == 1 and summary["confirmed_at_bug"] == 1
    assert summary["confirmed_at_bug_with_value"] == 2


def test_the_api_agent_everywhere_route_skips_value_hypotheses():
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="ESBMC_TIMEOUT")) == ()
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="ESBMC_TIMEOUT", oracle="")) == ("api_agent",)
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="PROPERTY_REJECTED", oracle="")) == ()


def test_the_report_counts_value_confirmations_by_location_apart():
    detection = Path("dataset/bugs_reais/funcao_com_bug/av_real_01.py")
    candidates = [Candidate(str(detection), "cli_bool_option", "", expression="assert isinstance(param, bool)")]
    result = {"verdict": "VALUE_CONFIRMED", "llm_calls": 1, "hypothesis": {
        "file": str(detection), "function": "cli_bool_option", "suspect_expression": "assert isinstance(param, bool)"}}
    evaluation = evaluate_verify([result], candidates, Path("dataset/bugs_reais/ground_truths.json"), [detection], [])
    assert evaluation["value_confirmed_by_location"]["expression"]["tp"] == 1
    assert evaluation["confirmed_by_location"]["expression"]["tp"] == 0


def test_the_agent_fallback_skips_value_hypotheses(tmp_path):
    from research_pipeline.verify.agent_arm import run_agent_fallback

    def agent(*args, **kwargs):
        raise AssertionError("the agent must not run on a value hypothesis")

    state = {}
    for oracle in ("value", ""):
        run_agent_fallback([_result("1", "x[i]", verdict="UNSUPPORTED", oracle=oracle)], run_agent=agent,
                           work_dir=tmp_path, esbmc_command=["esbmc"], bound=5, timeout_seconds=1, agent_timeout=1,
                           sources=None, state=state, save=lambda: None, config={})
        tried = len(state["agent_results"])
        assert tried == (0 if oracle else 1)


def test_level_summary_counts_value_confirmations_apart():
    from research_pipeline.verify.levels import ENGINE, consolidate, level_summary

    rows = consolidate([_result(h, "x[i]", verdict=v) for h, v in
                        (("1", "VALUE_CONFIRMED"), ("2", "VALUE_VIOLATION"), ("3", "PROPERTY_REJECTED"))]
                       + [_result("4", "x[i]", verdict="CONFIRMED", oracle="")])
    summary = level_summary(rows)
    assert summary["confirmed"] == 1 and summary["confirmed_by_level"] == {ENGINE: 1}
    assert summary["value_confirmed"] == 1 and summary["value_confirmed_by_level"] == {ENGINE: 1}
