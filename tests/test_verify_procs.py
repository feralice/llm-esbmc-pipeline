import os
import time
import sys
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


def test_direct_esbmc_timeout_reaps_children_and_keeps_partial_output(tmp_path):
    from research_pipeline.verification.esbmc_runner import run_esbmc_direct

    pidfile = tmp_path / "child.pid"
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(
        "import subprocess,sys,time\n"
        "from pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)\n"
        f"Path({str(pidfile)!r}).write_text(str(child.pid))\n"
        "print('VERIFICATION FAILED', flush=True)\n"
        "time.sleep(60)\n")
    result = run_esbmc_direct(tmp_path / "unused.py", esbmc_command=[sys.executable, str(wrapper)],
                              timeout_seconds=1, output_dir=tmp_path / "logs")
    child_pid = int(pidfile.read_text())
    try:
        assert result.status == "timeout"
        assert "VERIFICATION FAILED" in result.stdout
        assert not _alive(child_pid)
    finally:
        if _alive(child_pid):
            os.kill(child_pid, 9)


def test_independent_commands_do_not_kill_each_others_children(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from research_pipeline.verify.procs import run_command

    ready = tmp_path / 'ready'
    first = [sys.executable, '-c',
             f"from pathlib import Path; import time; Path({str(ready)!r}).touch(); time.sleep(0.3); print('first')"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(run_command, first, timeout=5)
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists()
        second = run_command([sys.executable, '-c', "import time; time.sleep(0.6); print('second')"], timeout=5)
        completed = future.result(timeout=6)
    assert second.returncode == completed.returncode == 0
    assert completed.stdout.strip() == 'first'
    assert second.stdout.strip() == 'second'
