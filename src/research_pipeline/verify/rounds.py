"""The agent's self-healing rounds, recorded by a stand-in ``esbmc`` placed first on its PATH.

Every call the agent makes to ESBMC becomes ``rounds/NNN/`` in the case folder (input.py, output.txt,
exit_code), so the rounds survive an agent that never finishes a harness. A call without a verdict also gets
a hint after ESBMC's own output (hint.txt): the installed ESBMC's README and passing tests that match the
refusal, or, on a crash, the instruction to stop."""

from __future__ import annotations

import json
import shlex
import shutil
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .esbmc_knowledge import KnowledgeIndex, Snippet, lookup

CRASH_EXIT_CODES = frozenset({134, 139})
TIMEOUT_EXIT_CODE = 124

_WRAPPER = """#!/bin/sh
rounds={rounds}
n=$(ls "$rounds" 2>/dev/null | wc -l)
dir=$(printf '%s/%03d' "$rounds" $((n + 1)))
mkdir -p "$dir"
for arg in "$@"; do
  case "$arg" in *.py) cp "$arg" "$dir/input.py"; break;; esac
done
{command} "$@" > "$dir/output.txt" 2>&1
code=$?
echo "$code" > "$dir/exit_code"
cat "$dir/output.txt"
PYTHONPATH={src} {python} -P -m research_pipeline.verify.rounds "$dir" {knowledge}
exit "$code"
"""
CRASH_HINT = ("ESBMC crashed: this is a bug in ESBMC, not in the harness, so do not work around it in the "
              "harness. Stop and report the crash.")
_ERROR_WORDS = ("ERROR", "error", "not supported", "Unsupported")


@dataclass
class Round:
    index: int
    source: str
    output: str
    exit_code: int
    kind: str  # verdict | refused | crash | timeout


def install_round_logger(case_dir: Path, esbmc: str | list[str], knowledge: KnowledgeIndex | None = None) -> Path:
    """Write ``case_dir/bin/esbmc``, which runs the configured ESBMC command (binary and flags), records
    the call and hints refusals from ``knowledge``; returns ``case_dir/bin``."""
    first, *flags = [esbmc] if isinstance(esbmc, str) else esbmc
    # Resolved now: a plain name looked up later would find this facade itself on the agent's PATH.
    binary = shutil.which(first) if "/" not in first else None
    command = shlex.join([str(Path(binary or first).resolve()), *flags])
    case_dir = Path(case_dir).resolve()
    bin_dir = case_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    index_path = bin_dir / "knowledge.json"
    index_path.write_text(json.dumps(asdict(knowledge or KnowledgeIndex(""))), encoding="utf-8")
    script = bin_dir / "esbmc"
    paths = {"rounds": case_dir / "rounds", "knowledge": index_path,
             "src": Path(__file__).resolve().parents[2], "python": sys.executable}
    script.write_text(_WRAPPER.format(command=command, **{k: shlex.quote(str(v)) for k, v in paths.items()}),
                      encoding="utf-8")
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


def round_hint(output: str, exit_code: int | None, knowledge: KnowledgeIndex) -> str:
    kind = classify_round(output, exit_code)
    if kind == "crash":
        return CRASH_HINT
    if kind != "refused":
        return ""
    errors = [line for line in output.splitlines() if any(word in line for word in _ERROR_WORDS)]
    found = lookup(knowledge, "\n".join(errors or output.splitlines()[-10:]), "")
    return f"What the installed ESBMC documents and accepts, matching this refusal:\n\n{found}" if found else ""


def _write_hint(folder: Path, index_path: Path) -> None:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    knowledge = KnowledgeIndex(data["commit"], [Snippet(**s) for s in data["sections"]],
                               [Snippet(**s) for s in data["tests"]])
    code = (folder / "exit_code").read_text(encoding="utf-8").strip()
    hint = round_hint((folder / "output.txt").read_text(encoding="utf-8", errors="replace"),
                      int(code) if code.lstrip("-").isdigit() else None, knowledge)
    if hint:
        (folder / "hint.txt").write_text(hint + "\n", encoding="utf-8")
        print(f"\n--- self-healing hint ---\n{hint}")


if __name__ == "__main__":
    _write_hint(Path(sys.argv[1]), Path(sys.argv[2]))
