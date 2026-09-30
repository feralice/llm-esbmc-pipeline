import json
from dataclasses import dataclass, field
from pathlib import Path

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify import loop
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.outcome import (
    CONFIRMED,
    GROUNDING_FAILED,
    MISSING_DEPENDENCY,
    NOT_CONFIRMED,
    SPEC_FAILED,
    UNSUPPORTED,
)
from research_pipeline.verify.replay import ReplayVerdict

SOURCE = "def ratio(total, count):\n    return total // count\n"
REPRODUCED = ReplayVerdict("reproduced", "ZeroDivisionError", 2)
GOOD = json.dumps({"params": {"total": "int", "count": "int"}, "attributes": {}, "assumptions": []})


@dataclass
class FakeLLM:
    replies: list[str]
    model: str = "fake"
    prompts: list[str] = field(default_factory=list)

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        self.prompts.append(user_prompt)
        return SynthResult(harness=self.replies.pop(0), raw_response="", model=self.model,
                           telemetry={"total_tokens": 10})


def _esbmc(*statuses, stdout=""):
    calls = []

    def run(path, esbmc_command=None, bound=5, timeout_seconds=30, output_dir=None, bound_flags=None, **_):
        assert bound_flags == ["--unwind", str(bound)]
        calls.append(Path(path).read_text())
        status = statuses[len(calls) - 1]
        kinds = ["uncaught exception: ZeroDivisionError"] if status == "violation_found" else []
        return ESBMCDirectResult(source_file=str(path), status=status, command=["esbmc"], returncode=1,
                                 summary=status, stdout=stdout,
                                 details={"violated_properties": kinds, "violated_files": [""] * len(kinds)})
    run.calls = calls
    return run


def _run(tmp_path, monkeypatch, llm, esbmc, replay=REPRODUCED, source=SOURCE,
         expression="total // count"):
    monkeypatch.setattr(loop, "run_esbmc_direct", esbmc)
    monkeypatch.setattr(loop, "concrete_replay", lambda program, function, **_: replay)
    hypothesis = BugHypothesis("r.py", "ratio", expression, category="division_by_zero")
    return loop.verify_hypothesis(hypothesis, llm=llm, source=source, esbmc_command=["esbmc"], bound=5,
                                  timeout_seconds=30, work_dir=tmp_path)


def test_first_attempt_confirmed(tmp_path, monkeypatch):
    esbmc = _esbmc("violation_found")
    result = _run(tmp_path, monkeypatch, FakeLLM([GOOD]), esbmc)
    assert result.verdict == CONFIRMED
    assert len(result.attempts) == 1
    assert "ratio(total, count)" in esbmc.calls[0]


def test_invalid_spec_is_repaired_with_the_problem_list(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"total": "dict"}}), GOOD])
    result = _run(tmp_path, monkeypatch, llm, _esbmc("violation_found"))
    assert result.verdict == CONFIRMED
    assert len(result.attempts) == 2
    assert "unsupported type 'dict'" in llm.prompts[1]
    assert "parameter 'count': missing type" in llm.prompts[1]


def test_conversion_error_is_repaired_with_esbmc_message(tmp_path, monkeypatch):
    llm = FakeLLM([GOOD, GOOD])
    esbmc = _esbmc("tool_error", "no_violation_found", stdout="ERROR: Type inference failed for total")
    result = _run(tmp_path, monkeypatch, llm, esbmc, replay=ReplayVerdict("not_reproduced"))
    assert result.verdict == NOT_CONFIRMED
    assert "Type inference failed" in llm.prompts[1]


def test_safe_result_is_never_retried(tmp_path, monkeypatch):
    llm = FakeLLM([GOOD, GOOD, GOOD])
    esbmc = _esbmc("no_violation_found")
    result = _run(tmp_path, monkeypatch, llm, esbmc, replay=ReplayVerdict("not_reproduced"))
    assert result.verdict == NOT_CONFIRMED
    assert len(esbmc.calls) == 1 and len(llm.prompts) == 1


def test_three_invalid_specs_give_spec_failed(tmp_path, monkeypatch):
    llm = FakeLLM(["nope", "nope", "nope"])
    result = _run(tmp_path, monkeypatch, llm, _esbmc())
    assert result.verdict == SPEC_FAILED
    assert len(result.attempts) == 3


def test_repairs_exhausted_on_conversion_error_give_unsupported(tmp_path, monkeypatch):
    llm = FakeLLM([GOOD, GOOD, GOOD])
    esbmc = _esbmc("tool_error", "tool_error", "tool_error", stdout="ERROR: unsupported: GeneratorExp")
    assert _run(tmp_path, monkeypatch, llm, esbmc).verdict == UNSUPPORTED


def test_missing_expression_costs_no_llm_call(tmp_path, monkeypatch):
    llm = FakeLLM([])
    result = _run(tmp_path, monkeypatch, llm, _esbmc(), expression="total / count")
    assert result.verdict == GROUNDING_FAILED
    assert llm.prompts == []


def test_undefined_helper_is_missing_dependency_before_llm(tmp_path, monkeypatch):
    llm = FakeLLM([])
    source = "def ratio(total, count):\n    return helper(total) // count\n"
    result = _run(tmp_path, monkeypatch, llm, _esbmc(), source=source, expression="helper(total) // count")
    assert result.verdict == MISSING_DEPENDENCY
    assert "helper" in result.reason
    assert llm.prompts == []


def test_hypothesis_is_identical_in_every_attempt(tmp_path, monkeypatch):
    llm = FakeLLM(["nope", GOOD])
    result = _run(tmp_path, monkeypatch, llm, _esbmc("violation_found"))
    assert result.to_dict()["hypothesis"]["hypothesis_id"] == BugHypothesis(
        "r.py", "ratio", "total // count", category="division_by_zero").hypothesis_id
    assert all("total // count" in prompt for prompt in llm.prompts)


def test_resample_strategy_never_shows_the_previous_error(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"total": "dict"}}), GOOD])
    monkeypatch.setattr(loop, "run_esbmc_direct", _esbmc("violation_found"))
    monkeypatch.setattr(loop, "concrete_replay", lambda program, function, **_: REPRODUCED)
    hypothesis = BugHypothesis("r.py", "ratio", "total // count", category="division_by_zero")
    result = loop.verify_hypothesis(hypothesis, llm=llm, source=SOURCE, esbmc_command=["esbmc"], bound=5,
                                    timeout_seconds=30, work_dir=tmp_path, strategy="resample")
    assert result.verdict == CONFIRMED
    assert len(llm.prompts) == 2
    assert llm.prompts[0] == llm.prompts[1]
    assert "rejected" not in llm.prompts[1]


def test_extra_spec_keys_are_recorded_and_cost_no_repair(tmp_path, monkeypatch):
    extra = json.dumps({"params": {"total": "int", "count": "int", "ghost": "int"},
                        "stubs": {"lib.nope": "int"}, "attributes": {}, "assumptions": []})
    result = _run(tmp_path, monkeypatch, FakeLLM([extra]), _esbmc("violation_found"))
    assert result.verdict == CONFIRMED and len(result.attempts) == 1
    assert result.attempts[0]["ignored"] == ["param ghost", "stub lib.nope"]
