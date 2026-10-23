"""The agent's self-healing rounds, recorded by a stand-in ``esbmc`` placed first on its PATH.

Every call the agent makes to ESBMC becomes ``rounds/NNN/`` in the case folder (input.py, output.txt,
exit_code), so the rounds survive an agent that never finishes a harness."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path

CRASH_EXIT_CODES = frozenset({134, 139})
TIMEOUT_EXIT_CODE = 124

_WRAPPER = """#!/bin/sh
rounds='{rounds}'
n=$(ls "$rounds" 2>/dev/null | wc -l)
dir=$(printf '%s/%03d' "$rounds" $((n + 1)))
mkdir -p "$dir"
for arg in "$@"; do
  case "$arg" in *.py) cp "$arg" "$dir/input.py"; break;; esac
done
'{esbmc}' "$@" > "$dir/output.txt" 2>&1
code=$?
echo "$code" > "$dir/exit_code"
cat "$dir/output.txt"
exit "$code"
"""


@dataclass
class Round:
    index: int
    source: str
    output: str
    exit_code: int
    kind: str  # verdict | refused | crash | timeout


def install_round_logger(case_dir: Path, esbmc: str) -> Path:
    """Write ``case_dir/bin/esbmc``, which runs the real ESBMC and records the call; returns ``case_dir/bin``."""
    case_dir = Path(case_dir).resolve()
    bin_dir = case_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "esbmc"
    script.write_text(_WRAPPER.format(rounds=case_dir / "rounds", esbmc=Path(esbmc).resolve()), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def classify_round(output: str, exit_code: int | None) -> str:
    """crash: exit 134/139 or a conversion failure; timeout: exit 124 or no exit code recorded (the
    call was killed); verdict: a VERIFICATION line; anything else is a refusal."""
    if exit_code in CRASH_EXIT_CODES or "Couldn't convert expression" in output:
        return "crash"
    if exit_code is None or exit_code == TIMEOUT_EXIT_CODE:
        return "timeout"
    return "verdict" if "VERIFICATION" in output else "refused"


def read_rounds(case_dir: Path) -> list[Round]:
    rounds = []
    for folder in sorted(path for path in (Path(case_dir) / "rounds").glob("*") if path.is_dir()):
        def text(name: str) -> str:
            file = folder / name
            return file.read_text(encoding="utf-8", errors="replace") if file.exists() else ""
        code = text("exit_code").strip()
        exit_code = int(code) if code.lstrip("-").isdigit() else None
        output = text("output.txt")
        rounds.append(Round(int(folder.name), text("input.py"), output,
                            -1 if exit_code is None else exit_code, classify_round(output, exit_code)))
    return rounds
