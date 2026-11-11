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
import threading
import time
from pathlib import Path

_PR_SET_CHILD_SUBREAPER = 36
# Linux subreaper status is process-wide. Serialize snapshots and cleanup so one
# command cannot mistake another concurrently running command's children for orphans.
_COMMAND_TREE_LOCK = threading.Lock()


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


def run_command(command: list[str], *, timeout: float, cwd: Path | None = None,
                env: dict | None = None) -> subprocess.CompletedProcess:
    """Run one command tree; TimeoutExpired retains its partial stdout and stderr."""
    started = time.monotonic()
    acquired = _COMMAND_TREE_LOCK.acquire(timeout=max(0.0, timeout))
    if not acquired:
        raise subprocess.TimeoutExpired(command, timeout)
    existing: set[int] | None = None
    try:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        _become_subreaper()
        existing = set(_descendants(os.getpid()))
        return subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, check=False,
                              start_new_session=True, timeout=remaining)
    finally:
        try:
            if existing is not None:
                _kill_leftovers(existing)
        finally:
            _COMMAND_TREE_LOCK.release()


def run_group(command: list[str], *, timeout_seconds: int, cwd: Path | None = None,
              env: dict | None = None) -> subprocess.CompletedProcess | None:
    """Compatibility interface for agents: None when the command tree times out."""
    try:
        return run_command(command, timeout=timeout_seconds, cwd=cwd, env=env)
    except subprocess.TimeoutExpired:
        return None
