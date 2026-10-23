import subprocess
from pathlib import Path

from research_pipeline.verify import esbmc_run
from research_pipeline.verify.agent_arm import AGENT_FAILED, ESBMC_CRASH, run_agent_arm
from research_pipeline.verify.rounds import install_round_logger, read_rounds
from tests.test_verify_agent_arm import PRESERVED, _esbmc, _hypothesis


def _fake_esbmc(tmp_path: Path, body: str) -> str:
    path = tmp_path / "fake_esbmc"
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def _call(logger_dir: Path, source: Path, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(logger_dir / "esbmc"), str(source), "--unwind", "5"], cwd=cwd,
                          capture_output=True, text=True, check=False)


def test_logger_records_each_call_and_passes_output_through(tmp_path):
    fake = _fake_esbmc(tmp_path, "echo 'VERIFICATION FAILED'; exit 1")
    bin_dir = install_round_logger(tmp_path, fake)
    for name, text in (("a.py", "x = 1\n"), ("b.py", "y = 2\n")):
        (tmp_path / name).write_text(text)
        done = _call(bin_dir, tmp_path / name, tmp_path)
        assert done.stdout == "VERIFICATION FAILED\n" and done.returncode == 1
    rounds = read_rounds(tmp_path)
    assert [r.index for r in rounds] == [1, 2]
    assert [r.source for r in rounds] == ["x = 1\n", "y = 2\n"]
    assert {r.kind for r in rounds} == {"verdict"} and rounds[0].exit_code == 1


def test_crash_exit_codes_are_classified(tmp_path):
    for number, body in enumerate(["exit 134", "exit 139", "echo \"Couldn't convert expression\"; exit 1"]):
        case = tmp_path / str(number)
        case.mkdir()
        (case / "h.py").write_text("pass\n")
        _call(install_round_logger(case, _fake_esbmc(tmp_path, body)), case / "h.py", case)
        assert [r.kind for r in read_rounds(case)] == ["crash"]


def test_refusal_without_verdict_is_refused(tmp_path):
    (tmp_path / "h.py").write_text("pass\n")
    bin_dir = install_round_logger(tmp_path, _fake_esbmc(tmp_path, "echo 'ERROR: unsupported'; exit 1"))
    _call(bin_dir, tmp_path / "h.py", tmp_path)
    assert [r.kind for r in read_rounds(tmp_path)] == ["refused"]


def test_killed_call_without_exit_code_is_a_timeout(tmp_path):
    folder = tmp_path / "rounds" / "001"
    folder.mkdir(parents=True)
    (folder / "input.py").write_text("pass\n")
    assert [r.kind for r in read_rounds(tmp_path)] == ["timeout"]


def _calling_agent(tmp_path: Path, harness: str | None):
    def run(prompt: str, cwd: Path, timeout_seconds: int) -> str:
        (cwd / "h.py").write_text("pass\n")
        _call(cwd / "bin", cwd / "h.py", cwd)
        if harness is not None:
            (cwd / "harness.py").write_text(harness, encoding="utf-8")
        return "DONE"
    return run


def test_agent_without_harness_keeps_its_rounds(tmp_path):
    fake = _fake_esbmc(tmp_path, "echo 'ERROR: unsupported'; exit 1")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_calling_agent(tmp_path, None),
                           esbmc_command=[fake], bound=5, timeout_seconds=30, log_rounds=True)
    assert result["verdict"] == AGENT_FAILED and result["reason"] == "agent wrote no harness.py"
    assert [(r["index"], r["kind"]) for r in result["rounds"]] == [(1, "refused")]
    assert "body_changed" in result["rounds"][0]["warnings"]
    assert result["esbmc_crash"] is False


def test_crash_round_never_confirms(tmp_path, monkeypatch):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    fake = _fake_esbmc(tmp_path, "exit 139")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work",
                           run_agent=_calling_agent(tmp_path, PRESERVED),
                           esbmc_command=[fake], bound=5, timeout_seconds=30, log_rounds=True)
    assert result["esbmc_crash"] is True and result["rounds"][-1]["kind"] == "crash"
    assert result["verdict"] == ESBMC_CRASH


def test_restarted_case_drops_rounds_left_by_an_earlier_attempt(tmp_path):
    stale = tmp_path / "work" / _hypothesis(tmp_path).hypothesis_id / "rounds" / "001"
    stale.mkdir(parents=True)
    (stale / "output.txt").write_text("VERIFICATION FAILED", encoding="utf-8")
    (stale / "exit_code").write_text("1", encoding="utf-8")
    fake = _fake_esbmc(tmp_path, "echo 'ERROR: unsupported'; exit 1")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_calling_agent(tmp_path, None),
                           esbmc_command=[fake], bound=5, timeout_seconds=30, log_rounds=True)
    assert [(r["index"], r["kind"]) for r in result["rounds"]] == [(1, "refused")]


def test_stale_harness_from_an_earlier_attempt_is_not_evaluated(tmp_path):
    case = tmp_path / "work" / _hypothesis(tmp_path).hypothesis_id
    case.mkdir(parents=True)
    (case / "harness.py").write_text(PRESERVED, encoding="utf-8")
    (case / "plugin_report.md").write_text("old", encoding="utf-8")
    result = run_agent_arm(_hypothesis(tmp_path), work_dir=tmp_path / "work", run_agent=_calling_agent(tmp_path, None),
                           esbmc_command=[_fake_esbmc(tmp_path, "exit 1")], bound=5, timeout_seconds=30, log_rounds=True)
    assert result["verdict"] == AGENT_FAILED and result["reason"] == "agent wrote no harness.py"
    assert not list(case.glob("plugin_*.md"))


def test_logger_runs_the_configured_command_with_its_flags(tmp_path):
    fake = _fake_esbmc(tmp_path, 'echo "args: $*"; echo VERIFICATION SUCCESSFUL')
    (tmp_path / "h.py").write_text("pass\n")
    done = _call(install_round_logger(tmp_path, [fake, "--python-strict-types"]), tmp_path / "h.py", tmp_path)
    assert done.stdout.startswith(f"args: --python-strict-types {tmp_path / 'h.py'} --unwind 5")
    assert [r.kind for r in read_rounds(tmp_path)] == ["verdict"]
