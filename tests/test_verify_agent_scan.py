from research_pipeline.verify import agent_scan
from research_pipeline.verify.hypothesis import BugHypothesis


def _h(name):
    return BugHypothesis(f"{name}.py", "f", "a // b", category="")


def test_agent_verifier_runs_each_hypothesis_and_reports_through_on_result(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(agent_scan, "run_agent_arm",
                        lambda h, **kw: {"hypothesis": h.to_dict(), "verdict": "CONFIRMED", "reason": "",
                                         "work_dir": str(kw["work_dir"])})
    verify = agent_scan.agent_verifier(lambda *a: "DONE", esbmc_command=["esbmc"], bound=5, timeout_seconds=30,
                                       agent_timeout=60)
    results = verify([_h("a"), _h("b")], llm=None, output_dir=tmp_path, completed={},
                     on_result=lambda i, d: seen.append(i))
    assert [r["verdict"] for r in results] == ["CONFIRMED", "CONFIRMED"] and seen == [0, 1]
    assert results[0]["work_dir"] == str(tmp_path / "agent_cases")


def test_agent_verifier_skips_completed_and_survives_a_failing_case(tmp_path, monkeypatch):
    calls = []

    def fake(h, **kw):
        calls.append(h.file)
        raise RuntimeError("agent crashed")

    monkeypatch.setattr(agent_scan, "run_agent_arm", fake)
    verify = agent_scan.agent_verifier(lambda *a: "DONE", esbmc_command=["esbmc"], bound=5, timeout_seconds=30,
                                       agent_timeout=60)
    done = {"hypothesis": _h("a").to_dict(), "verdict": "CONFIRMED", "reason": ""}
    results = verify([_h("a"), _h("b")], llm=None, output_dir=tmp_path, completed={0: done},
                     on_result=lambda i, d: None)
    assert calls == ["b.py"] and results[0] is done
    assert results[1]["verdict"] == "PIPELINE_ERROR" and "agent crashed" in results[1]["reason"]


def test_an_agent_session_that_broke_is_retried_on_resume_but_a_timeout_is_not(tmp_path, monkeypatch):
    reasons = iter(["agent did not finish: FileNotFoundError", "agent did not finish: TimeoutExpired"])
    monkeypatch.setattr(agent_scan, "run_agent_arm",
                        lambda h, **kw: {"hypothesis": h.to_dict(), "verdict": "AGENT_FAILED", "reason": next(reasons)})
    verify = agent_scan.agent_verifier(lambda *a: "DONE", esbmc_command=["esbmc"], bound=5, timeout_seconds=30,
                                       agent_timeout=60)
    results = verify([_h("a"), _h("b")], llm=None, output_dir=tmp_path, completed={}, on_result=lambda i, d: None)
    assert [r["verdict"] for r in results] == ["PIPELINE_ERROR", "AGENT_FAILED"]
