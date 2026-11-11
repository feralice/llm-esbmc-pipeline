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


def test_agent_timeout_is_part_of_the_verifier_label():
    from research_pipeline.verify.agent_scan import agent_verifier
    def label(seconds):
        return agent_verifier(lambda *a: "", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                              agent_timeout=seconds).label
    assert label(100) != label(1500)


def test_codex_agent_does_not_request_claude_skills_or_graph(tmp_path, monkeypatch):
    seen = {}
    def fake(h, **kwargs):
        seen.update(kwargs)
        return {"hypothesis": h.to_dict(), "verdict": "AGENT_FAILED", "reason": "test"}
    monkeypatch.setattr(agent_scan, "run_agent_arm", fake)
    verify = agent_scan.agent_verifier(lambda *a: "DONE", esbmc_command=["esbmc"], bound=5,
        timeout_seconds=30, agent_timeout=60, backend="codex", project_skills=False, skill=False)
    verify([_h("a")], llm=None, output_dir=tmp_path, completed={}, on_result=lambda i, d: None)
    assert seen["project_skills"] is False and seen["skill"] is False
    assert seen["log_rounds"] is False and seen["graph_tool"] is False
    assert "agent:codex:" in verify.label


def test_documentation_is_passed_as_context_and_changes_resume_label(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "api.md").write_text("Function f handles data.\n", encoding="utf-8")
    source = tmp_path / "a.py"
    source.write_text("def f(): pass\n", encoding="utf-8")
    seen = {}
    def fake(h, **kwargs):
        seen.update(kwargs)
        return {"hypothesis": h.to_dict(), "verdict": "AGENT_FAILED", "reason": "test"}
    monkeypatch.setattr(agent_scan, "run_agent_arm", fake)
    def make():
        return agent_scan.agent_verifier(lambda *a: "DONE", esbmc_command=["esbmc"], bound=5,
            timeout_seconds=30, agent_timeout=60, documentation_root=tmp_path)
    verify = make()
    h = BugHypothesis(str(source), "f", "f()")
    verify([h], llm=None, output_dir=tmp_path / "out", completed={}, on_result=lambda i, d: None)
    assert "docs/api.md:1" in seen["documentation"]
    (docs / "api.md").write_text("Function f changed.\n", encoding="utf-8")
    assert verify.label != make().label
