"""Validate under CPython using the generated program before compatibility rewrites."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .sandbox import host_replay_problem, process_limits

from .render import Program


@dataclass(frozen=True)
class ReplayVerdict:
    status: str  # reproduced | other_failure | not_reproduced | unavailable
    exception_type: str = ""
    line: int | None = None
    runs: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def concrete_replay(program: Program, function: str, *, max_runs: int = 400,
                    timeout_seconds: int = 20) -> ReplayVerdict:
    if program.replay_source is None and any(t.startswith("compat_") for t in program.transforms):
        return ReplayVerdict("unavailable", reason="rewritten program has no preserved replay source")
    source = program.source if program.replay_source is None else program.replay_source
    problem = host_replay_problem(source)
    if problem:
        return ReplayVerdict("unavailable", reason=f"not executed on host: {problem}")
    limits = process_limits(timeout_seconds)
    worker = Path(__file__).with_name("replay_worker.py")
    spans = program.target_spans if program.replay_target_spans is None else program.replay_target_spans
    target_range = program.target_range if program.replay_target_range is None else program.replay_target_range
    config = {"function": function, "spans": spans, "range": target_range,
              "max_runs": max_runs, "deadline_seconds": max(1, timeout_seconds - 3)}
    try:
        with tempfile.TemporaryDirectory(prefix="llm-esbmc-verify-") as temp_dir:
            directory = Path(temp_dir)
            (directory / "program.py").write_text(source, encoding="utf-8")
            (directory / "config.json").write_text(json.dumps(config), encoding="utf-8")
            output = directory / "result.json"
            completed = subprocess.run(
                [sys.executable, "-I", "-S", str(worker), "program.py", "config.json", str(output)],
                cwd=directory, env={}, capture_output=True, text=True,
                timeout=timeout_seconds, check=False, preexec_fn=limits,
            )
            if not output.exists():
                return ReplayVerdict("unavailable", reason=(completed.stderr or "no result")[-500:])
            data = json.loads(output.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired:
        return ReplayVerdict("unavailable", reason="replay timed out")
    return ReplayVerdict(
        status=str(data["status"]),
        exception_type=str(data.get("exception_type", "")),
        line=data.get("line"),
        runs=int(data.get("runs", 0)),
    )
