"""Run a command so that nothing it spawned outlives it.

Claude Code's Bash tool starts each shell with setsid, so the ESBMC an agent runs leaves the agent's
process group, and a tool call that times out orphans it to init. This process becomes a child
subreaper: orphans of its descendants are re-parented here instead, and are killed when the
command ends.
"""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
from pathlib import Path

_PR_SET_CHILD_SUBREAPER = 36


def _become_subreaper() -> None:
    try:
        ctypes.CDLL(None, use_errno=True).prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    except (OSError, AttributeError):
        pass  # not Linux: fall back to the process group alone


def _descendants(root: int) -> list[int]:
    children: dict[int, list[int]] = {}
    for entry in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if not entry.isdigit():
            continue
        try:
            stat = Path(f"/proc/{entry}/stat").read_text()
        except OSError:
            continue
        parent = int(stat.rsplit(")", 1)[1].split()[1])
        children.setdefault(parent, []).append(int(entry))
    found, pending = [], [root]
    while pending:
        for child in children.get(pending.pop(), []):
            found.append(child)
            pending.append(child)
    return found


def _kill_leftovers(existing: set[int]) -> None:
    for pid in _descendants(os.getpid()):
        if pid in existing:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        try:
            os.waitpid(pid, 0)  # an adopted orphan is our child now: reap it
        except ChildProcessError:
            pass


def run_group(command: list[str], *, timeout_seconds: int, cwd: Path | None = None,
              env: dict | None = None) -> subprocess.CompletedProcess | None:
    """None when the time runs out. Either way, every process the command left behind gets SIGKILL
    (ESBMC can ignore SIGTERM in the solver)."""
    _become_subreaper()
    existing = set(_descendants(os.getpid()))
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        _kill_leftovers(existing)  # an escaped descendant holding the pipe would block communicate()
        process.communicate()
        return None
    finally:
        _kill_leftovers(existing)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
