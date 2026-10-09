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
    rows, _ = _run([_r("a", "MISSING_DEPENDENCY")],
                   {"claude_agent": broken, "dynamic": lambda r: {"verdict": "FUZZ_NOTHING"}})
    assert rows[0]["steps"][0]["verdict"] == ARM_FAILED and rows[0]["final"] == "FUZZ_NOTHING"


def test_an_interrupted_case_resumes_after_its_last_finished_arm() -> None:
    calls = []

    def dynamic(_):
        calls.append("dyn")
        if calls.count("dyn") == 1:
            raise KeyboardInterrupt
        return {"verdict": "FUZZ_NOTHING"}
    arms = {"claude_agent": lambda r: calls.append("claude") or {"verdict": "UNSUPPORTED"}, "dynamic": dynamic}
    state = {}
    try:
        _run([_r("a", "MISSING_DEPENDENCY")], arms, state)
    except KeyboardInterrupt:
        pass
    rows, _ = _run([_r("a", "MISSING_DEPENDENCY")], arms, state)
    assert calls == ["claude", "dyn", "dyn"] and rows[0]["final"] == "FUZZ_NOTHING"


def test_a_failed_arm_is_retried_on_resume() -> None:
    attempts = []

    def flaky(_):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("rate limit")
        return {"verdict": "FUZZ_NOTHING"}
    _, state = _run([_r("a", "ESBMC_TIMEOUT")], {"dynamic": flaky})
    rows, _ = _run([_r("a", "ESBMC_TIMEOUT")], {"dynamic": flaky}, state)
    assert len(attempts) == 2 and rows[0]["final"] == "FUZZ_NOTHING"


def test_later_arms_see_earlier_steps_and_do_not_hide_a_dynamic_finding() -> None:
    seen = []
    arms = {"dynamic": lambda r: {"verdict": "FUZZ_FOUND"},
            "pinned": lambda r: seen.append([s["arm"] for s in r["steps"]]) or {"verdict": "PINNED_SAFE"}}
    rows, _ = _run([_r("a", "ESBMC_TIMEOUT")], arms)
    assert seen == [["dynamic"]] and rows[0]["final"] == "FUZZ_FOUND"


def test_resume_skips_finished_cases() -> None:
    calls = []
    arms = {"dynamic": lambda r: calls.append(1) or {"verdict": "FUZZ_NOTHING"}}
    _, state = _run([_r("a", "ESBMC_TIMEOUT")], arms)
    _run([_r("a", "ESBMC_TIMEOUT")], arms, state)
    assert calls == [1]
