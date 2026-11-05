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


def test_value_hypotheses_go_only_to_the_agent_arms():
    assert route(_result("1", "x[i]", verdict="ESBMC_TIMEOUT")) == ()
    assert route(_result("1", "x[i]", verdict="ESBMC_TIMEOUT", oracle="")) != ()
    assert route(_result("1", "x[i]", verdict="SPEC_FAILED")) == ("api_agent", "claude_agent")
    assert route(_result("1", "x[i]", verdict="UNSUPPORTED")) == ("claude_agent",)
    for verdict in ("VALUE_CONFIRMED", "VALUE_VIOLATION", "PROPERTY_REJECTED"):
        assert route(_result("1", "x[i]", verdict=verdict)) == ()


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


def test_the_api_agent_everywhere_route_takes_value_hypotheses_without_a_formal_verdict():
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="ESBMC_TIMEOUT")) == ("api_agent",)
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="VALUE_VIOLATION")) == ()
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


def test_the_agent_fallback_hands_a_value_hypothesis_the_engine_property(tmp_path, monkeypatch):
    from research_pipeline.verify import agent_arm

    seen = []
    monkeypatch.setattr(agent_arm, "run_agent_arm", lambda h, **kw: seen.append(kw) or {
        "hypothesis": h.to_dict(), "verdict": "AGENT_FAILED", "reason": ""})
    result = _result("1", "x[i]", verdict="UNSUPPORTED")
    result["attempts"] = [{"spec": '{"returns": "int", "postcondition": "result > 0"}'},
                          {"spec": '{"returns": "str", "postcondition": "len(result) > 0"}', "problems": ["bad"]}]
    agent_arm.run_agent_fallback([result], run_agent=None, work_dir=tmp_path, esbmc_command=["esbmc"], bound=5,
                                 timeout_seconds=1, agent_timeout=1, sources=None, state={}, save=lambda: None,
                                 config={})
    assert (seen[0]["returns"], seen[0]["postcondition"]) == ("int", "result > 0")


def test_level_summary_counts_value_confirmations_apart():
    from research_pipeline.verify.levels import ENGINE, consolidate, level_summary

    rows = consolidate([_result(h, "x[i]", verdict=v) for h, v in
                        (("1", "VALUE_CONFIRMED"), ("2", "VALUE_VIOLATION"), ("3", "PROPERTY_REJECTED"))]
                       + [_result("4", "x[i]", verdict="CONFIRMED", oracle="")])
    summary = level_summary(rows)
    assert summary["confirmed"] == 1 and summary["confirmed_by_level"] == {ENGINE: 1}
    assert summary["value_confirmed"] == 1 and summary["value_confirmed_by_level"] == {ENGINE: 1}
