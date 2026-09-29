from pathlib import Path

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


def _esbmc(status="violation_found"):
    def run(path, **_):
        kinds = ["uncaught exception: ZeroDivisionError"] if status == "violation_found" else []
        return ESBMCDirectResult(source_file=str(path), status=status, command=["esbmc"], returncode=1,
                                 summary=status, details={"violated_properties": kinds, "violated_files": [""] * len(kinds)})
    return run


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
    monkeypatch.setattr(agent_arm, "run_esbmc_direct", _esbmc())
    agent = _agent(PRESERVED)
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=agent,
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == CONFIRMED, result
    assert result["target_preserved"] is True
    assert result["replay"]["exception_type"] == "ZeroDivisionError"
    assert "total // count" in agent.calls[0] and "esbmc-verification" in agent.calls[0]
    assert "`esbmc harness.py --unwind 5" in agent.calls[0]


def test_dropping_a_statement_counts_as_rewrite(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_arm, "run_esbmc_direct", _esbmc())
    dropped = PRESERVED.replace("    lib.log(total)\n", "")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(dropped),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["target_preserved"] is False
    assert result["verdict"] == "AGENT_REWRITE_CONFIRMED"


def test_rewritten_target_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_arm, "run_esbmc_direct", _esbmc())
    rewritten = PRESERVED.replace("    return total // count", "    if count == 0:\n        count = 1\n    return total // count")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(rewritten),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["target_preserved"] is False
    assert result["verdict"] == UNVALIDATED


def test_missing_harness_is_agent_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_arm, "run_esbmc_direct", _esbmc())
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(None),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == AGENT_FAILED


def test_suspect_expression_missing_from_harness_is_agent_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_arm, "run_esbmc_direct", _esbmc())
    harness = PRESERVED.replace("total // count", "total + count")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_agent(harness),
                           esbmc_command=["esbmc"], bound=5, timeout_seconds=30)
    assert result["verdict"] == AGENT_FAILED
    assert "suspect expression" in result["reason"]
