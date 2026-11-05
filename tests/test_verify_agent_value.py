from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify import esbmc_run
from research_pipeline.verify.agent_arm import AGENT_FAILED, run_agent_arm
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.outcome import PROPERTY_REJECTED, UNVALIDATED, VALUE_CONFIRMED, VALUE_VIOLATION

ORIGINAL = "def magnitude(x):\n    return x if x > 0 else x\n"
HARNESS = '''from esbmc import nondet_int


def magnitude(x: int) -> int:
    return x if x > 0 else x


def main() -> None:
    x: int = nondet_int()
    _esbmc_result: int = magnitude(x)
    assert _esbmc_result >= 0


main()
'''


def _esbmc_hits_the_assert(path, **_):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    line = next((n for n, text in enumerate(lines, 1) if text.strip().startswith("assert ")), 0)
    return ESBMCDirectResult(source_file=str(path), status="violation_found", command=["esbmc"], returncode=1,
                             summary="violation_found",
                             details={"violated_properties": ["assertion"], "violated_files": [""],
                                      "violated_property_records": [{"kind": "assertion", "line": line}]})


@pytest.fixture(autouse=True)
def _fake_esbmc(monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc_hits_the_assert)


def _agent(harness):
    def run(prompt, cwd, timeout_seconds):
        run.prompts.append(prompt)
        (cwd / "harness.py").write_text(harness, encoding="utf-8")
        return "DONE"
    run.prompts = []
    return run


def _run(tmp_path, harness=HARNESS, fixed="def magnitude(x):\n    return x if x > 0 else -x\n",
         postcondition="result >= 0"):
    source = tmp_path / "m.py"
    source.write_text(ORIGINAL, encoding="utf-8")
    fixed_path = tmp_path / "fixed.py"
    fixed_path.write_text(fixed, encoding="utf-8")
    agent = _agent(harness)
    h = BugHypothesis(str(source), "magnitude", "x if x > 0 else x", oracle=VALUE_ORACLE)
    result = run_agent_arm(h, work_dir=tmp_path / "work", run_agent=agent, esbmc_command=["esbmc"], bound=5,
                           timeout_seconds=30, fixed_path=fixed_path, returns="int", postcondition=postcondition)
    return result, agent


def test_the_agent_harness_asserts_the_engine_property_and_the_fixed_version_keeps_it(tmp_path):
    result, agent = _run(tmp_path)
    assert result["verdict"] == VALUE_CONFIRMED, result
    assert result["replay"]["status"] == "property_violated" and result["control"]["status"] == "not_reproduced"
    assert "assert _esbmc_result >= 0" in agent.prompts[0] and "_esbmc_result: int = ..." in agent.prompts[0]


def test_a_property_the_fixed_version_also_breaks_is_rejected(tmp_path):
    result, _ = _run(tmp_path, fixed="def magnitude(x):\n    return x if x > 0 else x - 1\n")
    assert result["verdict"] == PROPERTY_REJECTED, result


def test_without_the_fixed_version_the_violation_stays_unconfirmed(tmp_path):
    source = tmp_path / "m.py"
    source.write_text(ORIGINAL, encoding="utf-8")
    h = BugHypothesis(str(source), "magnitude", "x if x > 0 else x", oracle=VALUE_ORACLE)
    result = run_agent_arm(h, work_dir=tmp_path / "work", run_agent=_agent(HARNESS), esbmc_command=["esbmc"],
                           bound=5, timeout_seconds=30, returns="int", postcondition="result >= 0")
    assert result["verdict"] == VALUE_VIOLATION


@pytest.mark.parametrize("harness", [
    HARNESS.replace("    assert _esbmc_result >= 0\n", ""),
    HARNESS.replace("assert _esbmc_result >= 0", "assert _esbmc_result > 0"),
    HARNESS.replace("    assert _esbmc_result >= 0\n", "    assert x == x\n    assert _esbmc_result >= 0\n"),
    HARNESS.replace("    assert _esbmc_result", "    _esbmc_result = -1\n    assert _esbmc_result"),
    HARNESS.replace("_esbmc_result: int = magnitude(x)", "_esbmc_result: int = -1"),
])
def test_a_harness_that_does_not_assert_the_property_on_the_call_is_refused(tmp_path, harness):
    result, _ = _run(tmp_path, harness=harness)
    assert result["verdict"] == AGENT_FAILED, result


def test_no_postcondition_means_no_agent_call(tmp_path):
    result, agent = _run(tmp_path, postcondition="")
    assert result["verdict"] == AGENT_FAILED and agent.prompts == []


def test_a_rewritten_target_cannot_confirm_a_wrong_result(tmp_path):
    rewritten = HARNESS.replace("    return x if x > 0 else x\n", "    y = 0\n    return x if x > 0 else x\n")
    result, _ = _run(tmp_path, harness=rewritten)
    assert result["target_preserved"] is False and result["verdict"] == UNVALIDATED
