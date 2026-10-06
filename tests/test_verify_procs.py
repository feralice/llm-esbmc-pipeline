import os
import time
from pathlib import Path

from research_pipeline.verify.procs import run_group


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_timeout_kills_the_grandchildren_too(tmp_path: Path) -> None:
    pidfile = tmp_path / "child.pid"
    script = tmp_path / "spawn.sh"
    # The grandchild ignores SIGTERM, like ESBMC stuck in the solver.
    script.write_text(f"#!/bin/sh\nsh -c 'trap \"\" TERM; sleep 300' &\necho $! > {pidfile}\nsleep 300\n")
    script.chmod(0o755)

    assert run_group([str(script)], timeout_seconds=2) is None

    time.sleep(0.5)
    assert not _alive(int(pidfile.read_text()))


def test_a_timeout_kills_a_grandchild_in_its_own_session(tmp_path: Path) -> None:
    # Claude Code's Bash tool starts each shell with setsid, so ESBMC leaves the agent's process group.
    pidfile = tmp_path / "child.pid"
    script = tmp_path / "spawn.sh"
    script.write_text(f"#!/bin/sh\nsetsid sh -c 'trap \"\" TERM; sleep 300' &\necho $! > {pidfile}\nsleep 300\n")
    script.chmod(0o755)

    assert run_group([str(script)], timeout_seconds=2) is None

    time.sleep(0.5)
    assert not _alive(int(pidfile.read_text()))


def test_an_orphan_left_by_a_finished_command_is_killed(tmp_path: Path) -> None:
    # A tool call that times out inside the agent orphans its ESBMC before the agent itself ends.
    pidfile = tmp_path / "child.pid"
    script = tmp_path / "orphan.sh"
    script.write_text(f"#!/bin/sh\nsetsid sh -c 'trap \"\" TERM; sleep 300' > /dev/null 2>&1 &\necho $! > {pidfile}\n")
    script.chmod(0o755)

    assert run_group([str(script)], timeout_seconds=10) is not None

    time.sleep(0.5)
    assert not _alive(int(pidfile.read_text()))


def test_a_finished_command_returns_its_output(tmp_path: Path) -> None:
    done = run_group(["sh", "-c", "echo ok"], timeout_seconds=10)
    assert done is not None and done.stdout.strip() == "ok"
