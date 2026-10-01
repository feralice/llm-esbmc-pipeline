from pathlib import Path

from research_pipeline.verify import esbmc_run
from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify import agent_arm
from research_pipeline.verify.agent_arm import AGENT_FAILED, run_agent_arm
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.outcome import CONFIRMED, UNVALIDATED

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
