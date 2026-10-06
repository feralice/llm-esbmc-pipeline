"""Run a command in its own process group so a timeout also stops what it spawned."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def run_group(command: list[str], *, timeout_seconds: int, cwd: Path | None = None,
              env: dict | None = None) -> subprocess.CompletedProcess | None:
    """None when the time runs out: the whole group gets SIGKILL (ESBMC can ignore SIGTERM in the solver)."""
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return None
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
