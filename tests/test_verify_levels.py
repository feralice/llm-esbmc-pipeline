import pytest

from research_pipeline.verify.levels import (
    AGENT,
    CONTEXT,
    CRASH,
    ENGINE,
    LANGUAGE,
    LLM_ONLY,
    LOCATE,
    SPEC,
    TIMEOUT,
    consolidate,
    level_summary,
    limit_group,
)


def _result(hid, verdict, reason=""):
    return {"hypothesis": {"hypothesis_id": hid, "file": f"{hid}.py", "function": "f"}, "verdict": verdict,
            "reason": reason}


@pytest.mark.parametrize(("verdict", "reason", "group"), [
    ("MISSING_DEPENDENCY", "undefined name(s): os, re", CONTEXT),
    ("UNSUPPORTED", "ERROR: Base class not found: OrderedDict", CONTEXT),
    ("UNSUPPORTED", "ERROR: TypeError at x.py 3: list indices must be integers or slices, not str", CONTEXT),
    ("UNSUPPORTED", "external call chain(...) uses *args/**kwargs", CONTEXT),
    ("UNSUPPORTED", "ERROR: Type inference failed for Assign at line 3", LANGUAGE),
    ("UNSUPPORTED", "ERROR: Cannot resolve nested attribute: __dict__", LANGUAGE),
    ("UNSUPPORTED", "ERROR: Function `py:x.py@C@A@F@__class__' not found", LANGUAGE),
    ("UNSUPPORTED", "async entry point is not supported", LANGUAGE),
    ("UNSUPPORTED", "ERROR: uncaught exception [N6type2t18symbolic_type_excpE]", CRASH),
    ("ESBMC_ERROR", "ESBMC direto: resultado inconclusivo.", CRASH),
    ("ESBMC_TIMEOUT", "", TIMEOUT),
    ("SPEC_FAILED", "The JSON was rejected", SPEC),
    ("GROUNDING_FAILED", "function 'g' not found", LOCATE),
    ("PIPELINE_ERROR", "RemoteDisconnected: Remote end closed connection", "network"),
    ("PIPELINE_ERROR", "KeyError: 'x'", "pipeline_error"),
    ("UNSUPPORTED", "ERROR: something no rule knows", "other"),
    ("UNSUPPORTED", "ERROR: Type inference failed at line 91. Variable XmlResponse not found", LANGUAGE),
])
def test_limit_group(verdict, reason, group):
    assert limit_group(verdict, reason) == group


def test_each_hypothesis_is_decided_by_the_first_level_with_an_esbmc_verdict():
    engine = [_result("a", "CONFIRMED"), _result("b", "UNSUPPORTED", "undefined name(s): os"),
              _result("c", "UNSUPPORTED", "undefined name(s): os"), _result("d", "MISSING_DEPENDENCY", "undefined name(s): x")]
    agent = [_result("b", "CONFIRMED"), _result("a", "NOT_CONFIRMED"),
             _result("c", "UNSUPPORTED", "ERROR: Type inference failed for Assign at line 9"),
             _result("d", "AGENT_FAILED", "agent wrote no harness.py")]
    rows = {r["hypothesis_id"]: r for r in consolidate(engine, agent)}
    assert (rows["a"]["level"], rows["a"]["verdict"]) == (ENGINE, "CONFIRMED")
    assert (rows["b"]["level"], rows["b"]["verdict"]) == (AGENT, "CONFIRMED")
    # The agent got past the context and hit a language limit: that is the reason recorded.
    assert (rows["c"]["level"], rows["c"]["limit"]) == (LLM_ONLY, LANGUAGE)
    assert (rows["d"]["level"], rows["d"]["limit"]) == (LLM_ONLY, CONTEXT)
    summary = level_summary(list(rows.values()))
    assert summary["by_level"] == {ENGINE: 1, AGENT: 1, LLM_ONLY: 2}
    assert summary["confirmed_by_level"] == {ENGINE: 1, AGENT: 1}
    assert summary["llm_only_by_limit"][LANGUAGE] == 1 and summary["llm_only_by_limit"][CONTEXT] == 1


def test_a_confirmation_through_a_simplified_function_has_its_own_level():
    rows = consolidate([_result("a", "UNSUPPORTED", "x")],
                       [{**_result("a", "CONFIRMED_SIMPLIFIED"), "target_preserved": False}])
    assert rows[0]["level"] == "esbmc_agent_simplified"
    summary = level_summary(rows)
    assert summary["confirmed"] == 0 and summary["confirmed_simplified"] == 1


def test_a_repeated_hypothesis_counts_once():
    rows = consolidate([_result("a", "CONFIRMED"), _result("a", "CONFIRMED")])
    assert level_summary(rows)["hypotheses"] == 1


def test_agent_verdict_on_a_rewritten_function_is_not_an_esbmc_verdict():
    agent = [{**_result("a", "NOT_CONFIRMED"), "target_preserved": False}]
    row = consolidate([_result("a", "UNSUPPORTED", "undefined name(s): os")], agent)[0]
    assert (row["level"], row["limit"]) == (LLM_ONLY, "agent_rewrote_function")


def test_repeated_hypothesis_keeps_the_occurrence_with_a_verdict():
    rows = consolidate([_result("a", "PIPELINE_ERROR", "KeyError"), _result("a", "CONFIRMED")])
    assert [(r["level"], r["verdict"]) for r in rows] == [(ENGINE, "CONFIRMED")]


def test_an_unclassified_agent_reason_does_not_override_the_engine_diagnosis():
    rows = consolidate([_result("a", "UNSUPPORTED", "undefined name(s): os")],
                       [_result("a", "UNSUPPORTED", "ERROR: something no rule knows")])
    assert rows[0]["limit"] == CONTEXT
