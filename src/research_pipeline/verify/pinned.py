"""Pinned arm: ESBMC checks only the path of an input the CPython search found to crash.

Each ``nondet_*`` call becomes a helper that returns the value at the current position of the
sequence and assumes away every other position. A sequence that does not match the program leaves
ESBMC no path, so only a violation counts; "safe" here is reported as PINNED_SAFE, never as a
verdict on the hypothesis."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

from .esbmc_run import check
from .outcome import ESBMC_MISSED, NOT_CONFIRMED, final_verdict
from .replay import concrete_replay
from .validation import program_for_result, replay_program_path

PINNED_SAFE = "PINNED_SAFE"
PINNED_UNAVAILABLE = "PINNED_UNAVAILABLE"

_CALL = re.compile(r"\bnondet_(int|float|bool|str|list)\(")
_DEFAULTS = {"int": "0", "float": "0.0", "bool": "False", "str": "''"}


def _literal(value) -> str | None:
    if type(value) in (int, bool, str) or (type(value) is float and math.isfinite(value)):
        return repr(value)
    return None


def _scalar_helper(kind: str, inputs: list) -> str:
    lines = [f"def _pin_{kind}() -> {kind}:", "    global _pin_cursor"]
    for position, value in enumerate(inputs):
        if type(value).__name__ == kind:
            lines += [f"    if _pin_cursor == {position}:", "        _pin_cursor += 1",
                      f"        return {repr(value)}"]
    return "\n".join(lines + ["    __ESBMC_assume(False)", f"    return {_DEFAULTS[kind]}", ""])


def _list_helper(inputs: list) -> str:
    """A list call takes its length then its elements; any int position may be a length."""
    lines = ["def _pin_list(size: int = 0, elem_type: int = 0) -> list:", "    global _pin_cursor"]
    for position, length in enumerate(inputs):
        elements = inputs[position + 1:position + 1 + length] if type(length) is int and length >= 0 else None
        if elements is None or len(elements) != length or len({type(e) for e in elements}) > 1:
            continue
        lines += [f"    if _pin_cursor == {position}:", f"        _pin_cursor += {length + 1}",
                  f"        return [{', '.join(repr(e) for e in elements)}]"]
    return "\n".join(lines + ["    __ESBMC_assume(False)", "    return []", ""])


def pin_program(source: str, inputs: list) -> str | None:
    """``source`` with every nondet call replaced by the value ``inputs`` gives it; None when a value
    has no Python literal (NaN, infinities, objects)."""
    if any(_literal(v) is None for v in inputs):
        return None
    kinds = sorted(set(_CALL.findall(source)))
    helpers = ["_pin_cursor: int = 0", ""]
    helpers += [_list_helper(inputs) if kind == "list" else _scalar_helper(kind, inputs) for kind in kinds]
    tree = ast.parse(source)
    body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))
            and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    at = body[0].lineno - 1 if body else len(source.splitlines())
    lines = _CALL.sub(lambda m: f"_pin_{m.group(1)}(", source).splitlines()
    return "\n".join(lines[:at] + helpers + lines[at:]) + "\n"


def _found_inputs(steps: list[dict]) -> list | None:
    for step in reversed(steps):
        if step.get("arm") == "dynamic" and step.get("verdict") == "FUZZ_FOUND":
            return (step.get("replay") or {}).get("inputs")
    return None


def pinned_check(result: dict, *, work_dir: Path, esbmc: str, bound: int, timeout_seconds: int) -> dict:
    """``result["steps"]`` holds the orchestrator's earlier arms; the pinned input is the dynamic arm's."""
    inputs = _found_inputs(result.get("steps") or [])
    if inputs is None or not result.get("program_path"):
        return {"verdict": PINNED_UNAVAILABLE, "reason": "no crashing input from the dynamic arm"}
    hypothesis = result["hypothesis"]
    pinned = pin_program(Path(result["program_path"]).read_text(encoding="utf-8"), inputs)
    replay_path = replay_program_path(result)
    program = None if replay_path is None else program_for_result(replay_path, hypothesis)
    if pinned is None or program is None:
        return {"verdict": PINNED_UNAVAILABLE, "reason": "input cannot be pinned or no replay program",
                "inputs": inputs}
    case_dir = Path(work_dir) / str(hypothesis.get("hypothesis_id", "case"))
    case_dir.mkdir(parents=True, exist_ok=True)
    path = case_dir / "pinned.py"
    path.write_text(pinned, encoding="utf-8")
    esbmc_result, reading, how = check(path, esbmc_command=[esbmc], bound=bound, timeout_seconds=timeout_seconds,
                                       work_dir=case_dir)
    replay = concrete_replay(program, hypothesis["function"].split(".")[-1], inputs=inputs)
    verdict = final_verdict(reading, replay)
    if verdict in {NOT_CONFIRMED, ESBMC_MISSED}:
        verdict = PINNED_SAFE  # may be no path at all: never a safety verdict
    return {"verdict": verdict, "reason": reading.message, "inputs": inputs, "replay": replay.to_dict(),
            "esbmc_status": esbmc_result.status, "pinned_path": str(path), **how}
