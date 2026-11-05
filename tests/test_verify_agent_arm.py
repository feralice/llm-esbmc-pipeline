import re
from pathlib import Path

from research_pipeline.verify import esbmc_run
from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify import agent_arm
import ast

import pytest

from research_pipeline.verify.agent_arm import (AGENT_FAILED, BEHAVIOUR_CHANGED, FIXED_ALSO_FAILS, HARNESS_BROKEN,
                                               NOT_CONFIRMED_VACUOUS, STUB_INDUCED, run_agent_arm, stub_cause)
from research_pipeline.llm.rate_limit import UsageLimitReached
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.outcome import CONFIRMED, NOT_CONFIRMED, UNVALIDATED
from research_pipeline.verify.replay import ReplayVerdict

ORIGINAL = "import lib\n\n\ndef ratio(total, count):\n    lib.log(total)\n    return total // count\n"

PRESERVED = '''from esbmc import nondet_int, assume


class lib:
    @staticmethod
    def log(a0: int) -> None:
        return None


def ratio(total: int, count: int) -> int:
    lib.log(total)
    return total // count


def main() -> None:
    t: int = nondet_int()
    c: int = nondet_int()
    ratio(t, c)


main()
'''


@pytest.fixture(autouse=True)
def _few_differential_runs(monkeypatch):
    monkeypatch.setattr(agent_arm, "DIFFERENTIAL_RUNS", 3)


@pytest.fixture(autouse=True)
def _pytest_calls(monkeypatch):
    """The generator would run the real ESBMC; each test sees what it was called with."""
    calls = []

    def fake(path, **kwargs):
        calls.append(kwargs)
        return {"status": "not_generated", "path": "", "reason": "fake", "route": "direct"}

    monkeypatch.setattr(agent_arm, "esbmc_pytest", fake)
    return calls


def _hypothesis(tmp_path: Path) -> BugHypothesis:
    source = tmp_path / "orig.py"
    source.write_text(ORIGINAL, encoding="utf-8")
    return BugHypothesis(str(source), "ratio", "total // count", category="division_by_zero")


def _esbmc(status="violation_found", stdout=""):
    def run(path, **_):
        kinds = ["uncaught exception: ZeroDivisionError"] if status == "violation_found" else []
        return ESBMCDirectResult(source_file=str(path), status=status, command=["esbmc"], returncode=1,
                                 summary=status, stdout=stdout,
                                 details={"violated_properties": kinds, "violated_files": [""] * len(kinds)})
    return run


# ESBMC's counterexample for the driver below: t = 7, c = 0.
TRACE = """[Counterexample]

State 1 file harness.py line 16 column 4 function main thread 0
----------------------------------------------------
  t = 7 (00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000111)

State 2 file harness.py line 17 column 4 function main thread 0
----------------------------------------------------
  c = 0 (00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000)
"""


def _agent(harness: str | None):
    calls = []

    def run(prompt: str, cwd: Path, timeout_seconds: int) -> str:
        calls.append(prompt)
        assert (cwd / "original.py").read_text(encoding="utf-8") == ORIGINAL
        if harness is not None:
            (cwd / "harness.py").write_text(harness, encoding="utf-8")
        return "DONE"
    run.calls = calls
    return run


def test_agent_harness_is_checked_independently_and_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    agent = _agent(PRESERVED)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == CONFIRMED, result
    assert result["target_preserved"] is True
    assert result["replay"]["exception_type"] == "ZeroDivisionError"
    assert "total // count" in agent.calls[0] and "esbmc-verification" in agent.calls[0]
    assert "`esbmc harness.py --unwind 5" in agent.calls[0]


def test_exception_raised_inside_an_invented_stub_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    stubbed = PRESERVED.replace("def ratio(", """class Count:
    def __rfloordiv__(self, other: int) -> int:
        return other // 0


def ratio(""").replace("    c: int = nondet_int()\n    ratio(t, c)", "    ratio(t, Count())")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(stubbed),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == STUB_INDUCED, result
    assert "Count.__rfloordiv__" in result["reason"]


def test_control_replays_the_fixed_version_with_the_same_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc(stdout=TRACE))
    guarded = tmp_path / "guarded.py"
    guarded.write_text(ORIGINAL.replace("    return total // count", "    return total // count if count else 0"))
    unguarded = tmp_path / "unguarded.py"
    unguarded.write_text(ORIGINAL.replace("return total // count", "return (total // count)"))
    def run(fixed):
        return run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / fixed.stem, run_agent=_agent(PRESERVED),
                             esbmc_command=["esbmc"], bound=5, timeout_seconds=30, fixed_path=fixed)
    assert run(guarded)["verdict"] == CONFIRMED
    assert run(unguarded)["verdict"] == FIXED_ALSO_FAILS


def test_exception_naming_an_invented_class_is_rejected():
    harness = ast.parse("class Other:\n    pass\n\n\ndef eq(a, b):\n    return len(b)\n")
    original = ast.parse("def eq(a, b):\n    return len(b)\n")
    replay = ReplayVerdict("reproduced", "TypeError", line=6, raised_at=6,
                           message="object of type 'Other' has no len()")
    assert "Other" in stub_cause(replay, harness, original)
    assert stub_cause(ReplayVerdict("reproduced", "KeyError", line=6, raised_at=6, message="3"),
                      harness, original) == ""


def test_simplified_function_confirms_only_when_esbmc_inputs_break_the_original(tmp_path, monkeypatch):
    dropped = PRESERVED.replace("    lib.log(total)\n", "")
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc(stdout=TRACE))
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(dropped),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["target_preserved"] is False and result["replayed_original_body"] is True
    assert result["verdict"] == "CONFIRMED_SIMPLIFIED", result
    # Without ESBMC's values the replay may not search on its own: nothing confirms.
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work2", run_agent=_agent(dropped),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == UNVALIDATED


def test_simplification_that_changes_behaviour_drops_the_confirmation(tmp_path, monkeypatch):
    changed = PRESERVED.replace("    lib.log(total)\n", "    if count == 7:\n        raise KeyError(count)\n")
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc(stdout=TRACE))
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(changed),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == BEHAVIOUR_CHANGED, result
    assert result["differential"]["preservation"] == "alterada"
    assert result["differential"]["divergences"][0]["harness"]["exception_type"] == "KeyError"


def test_confirmation_records_an_unmeasured_differential(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc(stdout=TRACE))
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == CONFIRMED, result
    # orig.py imports a module that does not exist, so only the stubs level runs.
    assert result["differential"]["level"] == "stubs"
    assert result["differential"]["preservation"] == "nao_medida"


def test_esbmc_inputs_that_do_not_break_the_original_do_not_confirm(tmp_path, monkeypatch):
    safe = TRACE.replace("c = 0 (00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000000)",
                         "c = 3 (00000000 00000000 00000000 00000000 00000000 00000000 00000000 00000011)")
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc(stdout=safe))
    dropped = PRESERVED.replace("    lib.log(total)\n", "")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(dropped),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] != "CONFIRMED_SIMPLIFIED"


def test_rewritten_target_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    rewritten = PRESERVED.replace("    return total // count", "    if count == 0:\n        count = 1\n    return total // count")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(rewritten),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["target_preserved"] is False
    assert result["verdict"] == UNVALIDATED


def test_missing_harness_is_agent_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(None),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == AGENT_FAILED


def test_suspect_expression_missing_from_harness_is_agent_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    harness = PRESERVED.replace("total // count", "total + count")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(harness),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == AGENT_FAILED
    assert "suspect expression" in result["reason"]


def test_api_agent_loops_on_esbmc_errors_until_a_verdict(tmp_path):
    from research_pipeline.verify.agent_arm import api_agent
    from research_pipeline.verify.llm_client import SynthResult

    esbmc = tmp_path / "fake_esbmc"
    esbmc.write_text("#!/bin/sh\nif grep -q fixed harness.py; then echo 'VERIFICATION FAILED'; "
                     "else echo 'ERROR: Object \"lib\" not found.'; fi\n", encoding="utf-8")
    esbmc.chmod(0o755)
    replies = iter(["no code here", "```python\nratio(1, 0)\n```", "```python\n# fixed\nratio(1, 0)\n```"])
    prompts = []

    class FakeLLM:
        def complete(self, system_prompt, user_prompt, *, json_mode=False):
            prompts.append(user_prompt)
            text = next(replies)
            code = text.split("```python\n")[1].split("```")[0] if "```python" in text else ""
            return SynthResult(harness=code, raw_response=text, model="fake", telemetry={})

    case = tmp_path / "case"
    case.mkdir()
    (case / "original.py").write_text(ORIGINAL, encoding="utf-8")
    run = api_agent(FakeLLM(), esbmc=str(esbmc))
    assert run("Goal: make ESBMC-Python run the function `ratio` ...", case, 60) == "DONE"
    assert "def ratio(total, count)" in prompts[0] and "ESBMC-Python" in prompts[0]
    assert "no python code block" in prompts[1]
    assert 'Object "lib" not found' in prompts[2] and "ratio(1, 0)" in prompts[2]
    assert "# fixed" in (case / "harness.py").read_text(encoding="utf-8")


def test_knowledge_from_the_esbmc_checkout_joins_the_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    notes = tmp_path / "notes.md"
    notes.write_text("# hand notes\n", encoding="utf-8")
    run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                  esbmc_command=["esbmc"], bound=5, timeout_seconds=30, notes=notes,
                  knowledge="### README: Limitations\nNo async.")
    written = next((tmp_path / "work").glob("*/ESBMC_PYTHON_NOTES.md")).read_text(encoding="utf-8")
    assert written.startswith("# hand notes") and "No async." in written


def test_project_skills_are_installed_in_the_case_folder(tmp_path):
    versions = agent_arm.install_project_skills(tmp_path)
    for name in ("regras-harness", "reparos-aprendidos"):
        assert (tmp_path / ".claude" / "skills" / name / "SKILL.md").is_file()
        assert re.fullmatch(r"[0-9a-f]{12}", versions[name])
    assert set(versions) == {"regras-harness", "reparos-aprendidos"}


def test_run_agent_arm_records_skill_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    agent = _agent(PRESERVED)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30, project_skills=True)
    assert set(result["skills"]) == {"regras-harness", "reparos-aprendidos"}
    assert "regras-harness" in agent.calls[0]


def test_confirmed_case_records_the_esbmc_pytest_and_its_values_lead_the_differential(tmp_path, monkeypatch):
    from research_pipeline.verify import differential as differential_module

    generated = tmp_path / "test_bug.py"
    generated.write_text('@pytest.mark.parametrize("t,c", [\n    (41, 0),\n])\ndef test_ratio(t, c):\n    ratio(t, c)\n')
    monkeypatch.setattr(agent_arm, "esbmc_pytest", lambda path, **kw: {
        "status": "reproduces", "path": str(generated), "reason": "", "route": "direct"})
    seen = {}
    real = differential_module.differential

    def spy(harness, original, h, seeds, **kwargs):
        seen["seeds"] = seeds
        return real(harness, original, h, seeds, **kwargs)

    monkeypatch.setattr(differential_module, "differential", spy)
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == CONFIRMED, result
    assert result["pytest"]["status"] == "reproduces" and result["pytest"]["route"] == "direct"
    assert seen["seeds"]["int"][:2] == [41, 0]


def test_a_pytest_that_does_not_reproduce_leaves_the_verdict_alone(tmp_path, monkeypatch, _pytest_calls):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == CONFIRMED
    assert result["pytest_esbmc"]["status"] == "not_generated" and result["pytest"]["route"] == "replay"
    assert _pytest_calls[0]["exception"] == "ZeroDivisionError"


def test_unconfirmed_case_does_not_run_the_pytest_generator(tmp_path, monkeypatch, _pytest_calls):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] != CONFIRMED and "pytest" not in result and not _pytest_calls


def _prompt(tmp_path: Path, **kwargs) -> str:
    agent = _agent(None)
    run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent, bound=5,
                  timeout_seconds=30, **kwargs)
    return agent.calls[0]


def test_prompt_names_the_recording_facade_only_when_rounds_are_logged(tmp_path):
    command = [str(tmp_path / "esbmc.sh"), "--python-strict-types"]
    logged = _prompt(tmp_path, esbmc_command=command, log_rounds=True)
    assert "`esbmc harness.py --unwind 5" in logged and "esbmc.sh" not in logged
    facade = (tmp_path / "work" / _hypothesis(tmp_path).hypothesis_id / "bin" / "esbmc").read_text(encoding="utf-8")
    assert f"{command[0]} --python-strict-types \"$@\"" in facade
    plain = _prompt(tmp_path, esbmc_command=command, log_rounds=False)
    assert f"`{command[0]} harness.py --unwind 5" in plain


@pytest.mark.parametrize("project_skills", [False, True])
@pytest.mark.parametrize("allow_simplify", [False, True])
def test_simplification_is_allowed_only_by_allow_simplify(tmp_path, project_skills, allow_simplify):
    prompt = _prompt(tmp_path, esbmc_command=["esbmc"], project_skills=project_skills, allow_simplify=allow_simplify)
    assert ("you may simplify" in prompt) is allow_simplify
    assert ("regras-harness" in prompt) is project_skills


def test_harness_skill_grants_no_simplification():
    text = (agent_arm.SKILLS_DIR / "regras-harness" / "SKILL.md").read_text(encoding="utf-8")
    assert "simplify" not in text and "unchanged" in text


def test_harness_rules_cover_the_2026_10_28_workarounds():
    text = (agent_arm.SKILLS_DIR / "regras-harness" / "SKILL.md").read_text(encoding="utf-8")
    assert "Version: 4" in text
    for needle in ("__ESBMC_", "elif", "lambda", "dict.get", "local variable"):
        assert needle in text


def test_recheck_writes_its_pytest_under_its_own_output_dir(tmp_path, monkeypatch, _pytest_calls):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    case = tmp_path / "case"
    case.mkdir()
    (case / "harness.py").write_text(PRESERVED, encoding="utf-8")
    verdict, _ = agent_arm.evaluate_harness(_hypothesis(tmp_path), PRESERVED, ORIGINAL, case, {},
                                            esbmc_command=["esbmc"], bound=5, timeout_seconds=30,
                                            output_dir=tmp_path / "recheck")
    assert verdict == CONFIRMED
    assert _pytest_calls[0]["out_dir"] == tmp_path / "recheck" / "pytest"


def test_fallback_with_an_esbmc_checkout_runs_the_agent(tmp_path):
    from research_pipeline.verify.agent_arm import run_agent_fallback

    checkout = tmp_path / "esbmc"
    (checkout / "src/python-frontend").mkdir(parents=True)
    (checkout / "src/python-frontend/README.md").write_text("## Types\n\nAnnotate parameters.\n", encoding="utf-8")
    binary = checkout / "build" / "esbmc"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    h = _hypothesis(tmp_path)
    result = {"hypothesis": h.to_dict(), "verdict": "UNSUPPORTED", "reason": "ERROR: annotate parameters"}
    [data] = run_agent_fallback([result], run_agent=lambda prompt, cwd, timeout: "DONE", work_dir=tmp_path / "work",
                                esbmc_command=[str(binary)], bound=5, timeout_seconds=1, agent_timeout=1,
                                sources=None, state={}, save=lambda: None, config={})
    assert data["reason"] == "agent wrote no harness.py"


# The nm_real_12 shape: the target is intact, but the driver never calls it, so "safe" says nothing.
VACUOUS = PRESERVED.replace("    ratio(t, c)\n", "    assume(t != t)\n    ratio(t, c)\n")


def _agent_sequence(*harnesses: str):
    calls = []

    def run(prompt: str, cwd: Path, timeout_seconds: int) -> str:
        calls.append(prompt)
        (cwd / "harness.py").write_text(harnesses[min(len(calls), len(harnesses)) - 1], encoding="utf-8")
        return "DONE"
    run.calls = calls
    return run


def _reach(*answers: str):
    seen = []

    def reach(program, **_):
        seen.append(program)
        return answers[min(len(seen), len(answers)) - 1]
    reach.seen = seen
    return reach


def test_safe_verdict_whose_bug_line_is_unreachable_is_vacuous(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    reach = _reach("unreachable")
    monkeypatch.setattr(agent_arm, "reachability", reach)
    agent = _agent_sequence(VACUOUS)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == NOT_CONFIRMED_VACUOUS, result
    assert result["reachability"] == "unreachable"
    target_line = VACUOUS.splitlines().index("    return total // count") + 1
    assert reach.seen[0].target_spans[0][0] == target_line
    assert "from esbmc import" in reach.seen[0].source  # ESBMC, not CPython, runs the probe


def test_safe_verdict_that_reaches_the_bug_line_stays_not_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    monkeypatch.setattr(agent_arm, "reachability", _reach("reachable"))
    agent = _agent_sequence(VACUOUS)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == NOT_CONFIRMED, result
    assert result["reachability"] == "reachable"
    assert len(agent.calls) == 1


def test_vacuous_harness_goes_back_to_the_agent_once_with_the_reason(tmp_path, monkeypatch):
    safe, dirs = _esbmc("no_violation_found"), []

    def recording(path, **kwargs):
        dirs.append(kwargs["output_dir"])
        return safe(path, **kwargs)
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", recording)
    monkeypatch.setattr(agent_arm, "reachability", _reach("unreachable", "reachable"))
    agent = _agent_sequence(VACUOUS, PRESERVED)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30, retry=True)
    assert len(agent.calls) == 2
    retry_prompt = agent.calls[1]
    assert retry_prompt.startswith(agent.calls[0])  # a fresh session: the task and its rules come again
    assert "never reaches" in retry_prompt and "assume(t != t)" in retry_prompt
    # The retried driver reaches the division; the faked ESBMC says safe while CPython raises there.
    assert result["verdict"] == "ESBMC_MISSED" and result["retried"] is True
    assert result["first_attempt"]["verdict"] == NOT_CONFIRMED_VACUOUS
    assert result["first_attempt"]["reachability"] == "unreachable" and "reachability" not in result
    case = tmp_path / "work" / _hypothesis(tmp_path).hypothesis_id
    assert (case / "harness_first.py").read_text(encoding="utf-8") == VACUOUS
    assert [d.parent for d in dirs] == [case, case / "retry"]  # the retry keeps the first ESBMC logs


def test_no_retry_unless_asked(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    monkeypatch.setattr(agent_arm, "reachability", _reach("unreachable"))
    agent = _agent_sequence(VACUOUS)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert len(agent.calls) == 1 and result["retried"] is False
    assert result["verdict"] == NOT_CONFIRMED_VACUOUS


def test_retry_budget_is_one(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    monkeypatch.setattr(agent_arm, "reachability", _reach("unreachable"))
    agent = _agent_sequence(VACUOUS)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30, retry=True)
    assert len(agent.calls) == 2
    assert result["verdict"] == NOT_CONFIRMED_VACUOUS


def test_retry_that_does_not_finish_keeps_the_first_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    monkeypatch.setattr(agent_arm, "reachability", _reach("unreachable"))
    first = _agent_sequence(VACUOUS)

    def agent(prompt, cwd, timeout_seconds):
        if first.calls:
            raise agent_arm.subprocess.TimeoutExpired("claude", timeout_seconds)
        return first(prompt, cwd, timeout_seconds)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30, retry=True)
    assert result["verdict"] == NOT_CONFIRMED_VACUOUS and "retry did not finish" in result["reason"]
    assert result["reachability"] == "unreachable" and result["target_preserved"] is True


def test_changed_body_goes_back_unless_simplifying_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    rewritten = PRESERVED.replace("    return total // count", "    if count == 0:\n        count = 1\n    return total // count")

    def run(work: str, **kwargs):
        agent = _agent_sequence(rewritten, PRESERVED)
        result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / work, run_agent=agent,
                               esbmc_command=["esbmc"], bound=5, timeout_seconds=30, retry=True, **kwargs)
        return result, agent
    reach = _reach("unreachable")
    monkeypatch.setattr(agent_arm, "reachability", reach)
    result, agent = run("strict")
    assert len(agent.calls) == 2 and "differs from original.py" in agent.calls[1]
    assert result["first_attempt"]["target_preserved"] is False and result["target_preserved"] is True
    assert "reachability" not in result["first_attempt"]  # the probe needs the original body
    assert reach.seen == []  # and the retry reproduced the division, so it was not needed
    result, agent = run("simplify", allow_simplify=True)
    assert len(agent.calls) == 1 and result["retried"] is False


def test_probe_uses_the_safe_run_unwind_and_every_occurrence(tmp_path, monkeypatch):
    original = "def ratio(total, count):\n    if total:\n        return total // count\n    return total // count\n"
    source = tmp_path / "two.py"
    source.write_text(original, encoding="utf-8")
    h = BugHypothesis(str(source), "ratio", "total // count", category="division_by_zero")
    harness = ("from esbmc import nondet_int\n\n\n" + original +
               "\n\ndef main() -> None:\n    ratio(nondet_int(), nondet_int())\n\n\nmain()\n")
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    calls = []

    def reach(program, *, unwind, **_):
        calls.append((program.target_spans, unwind))
        return "unreachable" if len(calls) == 1 else "reachable"
    monkeypatch.setattr(agent_arm, "reachability", reach)
    monkeypatch.setattr(agent_arm, "concrete_replay", lambda *a, **k: ReplayVerdict("not_reproduced"))
    result = run_agent_arm(h, work_dir=tmp_path / "work", run_agent=_agent_sequence(harness),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert [spans for spans, _ in calls] == [((6, 6),), ((7, 7),)]
    assert {unwind for _, unwind in calls} == {5}
    assert result["reachability"] == "reachable" and result["verdict"] == NOT_CONFIRMED


def _no_esbmc(*_args, **_kwargs):
    raise AssertionError("ESBMC must not run on a harness that breaks under CPython")


def _evaluate(tmp_path, harness):
    case = tmp_path / "case"
    case.mkdir()
    (case / "harness.py").write_text(harness, encoding="utf-8")
    result = {}
    verdict, reason = agent_arm.evaluate_harness(_hypothesis(tmp_path), harness, ORIGINAL, case, result,
                                                 esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    return verdict, reason, result


def test_stub_that_raises_outside_the_target_is_harness_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _no_esbmc)
    harness = PRESERVED.replace("    ratio(t, c)", "    [][0]\n    ratio(t, c)")
    verdict, reason, result = _evaluate(tmp_path, harness)
    assert verdict == HARNESS_BROKEN
    assert "IndexError at line 18" in reason
    assert result["smoke"]["status"] == "other_failure"


def test_exception_at_the_suspect_line_still_goes_to_esbmc(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    assert _evaluate(tmp_path, PRESERVED)[0] == CONFIRMED


def test_exception_inside_the_target_off_the_suspect_line_is_not_harness_broken(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", lambda path, **kw: calls.append(path) or _esbmc()(path))
    verdict, _, _ = _evaluate(tmp_path, PRESERVED.replace("    lib.log(total)\n", "    [][total]\n"))
    assert verdict != HARNESS_BROKEN and calls


def test_harness_broken_goes_back_to_the_agent():
    assert agent_arm.retry_reason(HARNESS_BROKEN, "x", {}, False) == "x"


def test_confirmation_without_esbmc_pytest_gets_one_from_the_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    verdict, _, result = _evaluate(tmp_path, PRESERVED)
    assert verdict == CONFIRMED
    assert result["pytest"]["route"] == "replay" and result["pytest"]["status"] == "reproduces"
    assert result["pytest_esbmc"]["status"] == "not_generated"
    assert Path(result["pytest"]["path"]).name == "test_replay.py"


def test_driver_that_breaks_on_one_input_but_reaches_the_bug_on_another_goes_to_esbmc(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    harness = PRESERVED.replace("    ratio(t, c)", "    if t == 0:\n        [][0]\n    ratio(t, c)")
    assert _evaluate(tmp_path, harness)[0] == CONFIRMED


def test_reachability_probe_runs_with_the_library_unwinding(tmp_path, monkeypatch):
    seen = []
    safe = ESBMCDirectResult(source_file="h.py", status="no_violation_found", command=["esbmc"], returncode=0,
                             summary="", details={})
    monkeypatch.setattr(agent_arm, "check", lambda *a, **k: (safe, esbmc_run.classify_esbmc(safe),
                                                              {"unwind": 5, "library_unwind": 64,
                                                               "library_loops": ["strlen:0"]}))
    monkeypatch.setattr(agent_arm, "reachability", lambda program, **kw: seen.append(kw["esbmc"]) or "REACHABLE")
    harness = PRESERVED.replace("    ratio(t, c)", "    if c != 0:\n        ratio(t, c)")
    _evaluate(tmp_path, harness)
    assert seen and seen[0][-2:] == ["--unwindsetname", "strlen:0:64"]


@pytest.mark.parametrize("graph_tool", [True, False])
def test_graph_tool_is_installed_and_named_in_the_prompt(tmp_path, monkeypatch, graph_tool):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    prompts = []

    def agent(prompt, cwd, timeout):
        prompts.append(prompt)
        (cwd / "harness.py").write_text(PRESERVED, encoding="utf-8")
        return "DONE"

    h = _hypothesis(tmp_path)
    run_agent_arm(h, work_dir=tmp_path / "work", run_agent=agent, esbmc_command=["esbmc"], bound=5,
                  timeout_seconds=30, graph_tool=graph_tool)
    case = tmp_path / "work" / h.hypothesis_id
    assert (case / "graph.py").exists() is graph_tool and (case / "graph.json").exists() is graph_tool
    assert ("python3 graph.py" in prompts[0]) is graph_tool


@pytest.mark.parametrize("graph_tool", [True, False])
def test_claude_agent_may_run_graph_py_only_with_the_graph_tool(tmp_path, monkeypatch, graph_tool):
    seen = []
    monkeypatch.setattr(agent_arm, "run_group", lambda command, **kw: seen.append(command) or None)
    run = agent_arm.claude_agent(esbmc="/x/esbmc", graph_tool=graph_tool)
    with pytest.raises(Exception):
        run("p", tmp_path, 1)
    assert ("Bash(python3 graph.py:*)" in seen[0]) is graph_tool


def test_api_agent_refuses_the_graph_tool():
    with pytest.raises(ValueError, match="graph"):
        agent_arm.make_agent("openai", model="m", esbmc="esbmc", bound=5, graph_tool=True)


def test_an_api_error_from_the_agent_session_is_a_pipeline_error(tmp_path):
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work",
                           run_agent=lambda prompt, cwd, timeout: "API Error: Can't reach the API server (EAI_AGAIN)",
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == "PIPELINE_ERROR"
    assert "EAI_AGAIN" in result["reason"]


def test_a_usage_limit_from_the_agent_session_stops_the_run(tmp_path):
    with pytest.raises(UsageLimitReached, match="monthly spend limit"):
        run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work",
                      run_agent=lambda prompt, cwd, timeout: "You've hit your monthly spend limit · raise it",
                      esbmc_command=["esbmc"], bound=5, timeout_seconds=30)


def test_cpython_reproduction_counts_apart_when_esbmc_reaches_no_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("tool_error"))
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == agent_arm.REPRODUCED_CPYTHON, result
    assert result["replay"]["exception_type"] == "ZeroDivisionError"
    assert result["pytest"]["status"] == "reproduces", result["pytest"]


def test_cpython_reproduction_goes_through_the_fixed_version_control(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("tool_error"))
    unguarded = tmp_path / "unguarded.py"
    unguarded.write_text(ORIGINAL.replace("return total // count", "return (total // count)"))
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30, fixed_path=unguarded)
    assert result["verdict"] == FIXED_ALSO_FAILS, result


def test_cpython_reproduction_inside_an_invented_stub_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("tool_error"))
    stubbed = PRESERVED.replace("def ratio(", """class Count:
    def __rfloordiv__(self, other: int) -> int:
        return other // 0


def ratio(""").replace("    c: int = nondet_int()\n    ratio(t, c)", "    ratio(t, Count())")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(stubbed),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == STUB_INDUCED, result


def test_a_safe_esbmc_verdict_is_not_overridden_by_cpython(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("no_violation_found"))
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(PRESERVED),
                           esbmc_command=None, bound=5, timeout_seconds=30)
    assert result["verdict"] != agent_arm.REPRODUCED_CPYTHON, result
