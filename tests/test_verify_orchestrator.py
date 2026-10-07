from research_pipeline.verify.orchestrator import ARM_FAILED, orchestrate


def _r(hid: str, verdict: str, reason: str = "") -> dict:
    return {"hypothesis": {"hypothesis_id": hid}, "verdict": verdict, "reason": reason}


def _run(results, arms, state=None):
    state = {} if state is None else state
    return orchestrate(results, arms=arms, state=state, save=lambda: None), state


def test_a_formal_verdict_stops_the_sequence_and_fuzz_found_does_not() -> None:
    calls = []
    arms = {"api_agent": lambda r: calls.append("api") or {"verdict": "UNSUPPORTED"},
            "claude_agent": lambda r: calls.append("claude") or {"verdict": "CONFIRMED"},
            "dynamic": lambda r: calls.append("dyn") or {"verdict": "FUZZ_FOUND"}}
    rows, _ = _run([_r("a", "SPEC_FAILED")], arms)
    assert calls == ["api", "claude"] and rows[0]["final"] == "CONFIRMED"


def test_done_results_run_no_arm_and_missing_arms_are_skipped() -> None:
    rows, _ = _run([_r("a", "CONFIRMED"), _r("b", "MISSING_DEPENDENCY")],
                   {"dynamic": lambda r: {"verdict": "FUZZ_NOTHING"}})
    assert rows[0]["steps"] == [] and rows[0]["final"] == "CONFIRMED"
    assert [s["arm"] for s in rows[1]["steps"]] == ["dynamic"] and rows[1]["final"] == "FUZZ_NOTHING"


def test_an_arm_that_raises_is_recorded_and_the_next_one_runs() -> None:
    def broken(_):
        raise RuntimeError("boom")
    rows, _ = _run([_r("a", "SPEC_FAILED")], {"api_agent": broken, "dynamic": lambda r: {"verdict": "FUZZ_NOTHING"}})
    assert rows[0]["steps"][0]["verdict"] == ARM_FAILED and rows[0]["final"] == "FUZZ_NOTHING"


def test_resume_skips_finished_cases() -> None:
    calls = []
    arms = {"dynamic": lambda r: calls.append(1) or {"verdict": "FUZZ_NOTHING"}}
    _, state = _run([_r("a", "ESBMC_TIMEOUT")], arms)
    _run([_r("a", "ESBMC_TIMEOUT")], arms, state)
    assert calls == [1]
