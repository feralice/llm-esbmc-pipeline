"""Validate under CPython using the generated program before compatibility rewrites."""

from __future__ import annotations

import functools
import json
import re
import shutil
import struct
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


# A module-level state has no "function" part.
_STATE = re.compile(r"^State \d+ .*?(?:\bfunction (\S+) )?thread", re.M)
# The value as printed, then its bits: floats print rounded (-0.000000), so their bits are decoded.
_NUMBER = re.compile(r"^\s+[\w.\[\]]+ = (-?\d+(?:\.\d+)?(?:e[+-]?\d+)?) \(([01 ]+)\)", re.M)


def _number(text: str, bits: str) -> tuple[str, int | float]:
    raw = bits.replace(" ", "")
    if "." in text or "e" in text:
        if len(raw) == 64:
            return "float", struct.unpack(">d", int(raw, 2).to_bytes(8, "big"))[0]
        return "float", float(text)
    return "int", int(text)
_MAX_SEEDS = 8


def counterexample_seeds(output: str, driver: str | None) -> dict[str, list]:
    """Numbers ESBMC's counterexamples give the driver's inputs (any function's when ``driver`` is
    None): replay tries them before its small defaults. They only steer the search; a confirmation
    still needs CPython to raise at the target."""
    seeds: dict[str, list] = {"int": [], "float": []}
    states = list(_STATE.finditer(output))
    for state, following in zip(states, [*states[1:], None]):
        if driver is not None and state.group(1) != driver:
            continue
        block = output[state.end():following.start() if following else len(output)]
        for text, bits in _NUMBER.findall(block):
            kind, value = _number(text, bits)
            if value not in seeds[kind] and len(seeds[kind]) < _MAX_SEEDS:
                seeds[kind].append(value)
    return seeds


@functools.cache
def _no_network_prefix() -> tuple[str, ...]:
    """Run the replay in a new network namespace when the host allows it (unprivileged unshare)."""
    command = ("unshare", "--user", "--map-root-user", "--net")
    if shutil.which("unshare") is None:
        return ()
    try:
        probe = subprocess.run([*command, "true"], capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    return command if probe.returncode == 0 else ()


def concrete_replay(program: Program, function: str, *, max_runs: int = 400,
                    timeout_seconds: int = 20, seeds: dict[str, list] | None = None,
                    seeds_only: bool = False) -> ReplayVerdict:
    """``seeds_only`` runs ESBMC's counterexample values alone: a reproduction then shows those inputs,
    not a search of its own, break the program."""
    if seeds_only and not any((seeds or {}).values()):
        return ReplayVerdict("unavailable", reason="no counterexample values to replay")
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
              "max_runs": max_runs, "deadline_seconds": max(1, timeout_seconds - 3), "seeds": seeds or {},
              "seeds_only": seeds_only}
    try:
        with tempfile.TemporaryDirectory(prefix="llm-esbmc-verify-") as temp_dir:
            directory = Path(temp_dir)
            (directory / "program.py").write_text(source, encoding="utf-8")
            (directory / "config.json").write_text(json.dumps(config), encoding="utf-8")
            output = directory / "result.json"
            completed = subprocess.run(
                [*_no_network_prefix(), sys.executable, "-I", "-S", str(worker), "program.py", "config.json",
                 str(output)],
                cwd=directory, env={}, capture_output=True, text=True,
                timeout=timeout_seconds, check=False, preexec_fn=limits,
            )
            if not output.exists():
                return ReplayVerdict("unavailable", reason=(completed.stderr or "no result")[-500:])
            data = json.loads(output.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired:
        return ReplayVerdict("unavailable", reason="replay timed out")
    line = data.get("line")
    inside = isinstance(line, int) and any(start <= line <= end for start, end in spans) and (
        not target_range[1] or target_range[0] <= line <= target_range[1])
    if data.get("status") == "reproduced" and not inside:
        # The worker shares its process with the program it runs: a claim outside the target is not trusted.
        return ReplayVerdict("unavailable", reason=f"replay reported line {line} outside the hypothesis")
    return ReplayVerdict(
        status=str(data["status"]),
        exception_type=str(data.get("exception_type", "")),
        line=data.get("line"),
        runs=int(data.get("runs", 0)),
    )
