"""LLM-input arm: when the CPython search finds no crash, an LLM proposes the nondet values.

The proposal is only a candidate: it counts when the replay of the original code, fed exactly those
values, raises at the suspect expression. The pinned arm then has ESBMC check that one path."""

from __future__ import annotations

import json
from pathlib import Path

from .dynamic import FUZZ_FOUND
from .replay import concrete_replay
from .validation import program_for_result, replay_program_path

LLM_INPUT_NOTHING = "LLM_INPUT_NOTHING"
LLM_INPUT_UNAVAILABLE = "LLM_INPUT_UNAVAILABLE"

_SYSTEM = """You find concrete inputs that make a Python program crash.
The program draws every input from these calls, in execution order:
nondet_int(), nondet_float(), nondet_bool(), nondet_str() each consume one value of that type;
nondet_list(size, elem_type) consumes one int (the length, 0..size) and then that many elements.
Booleans are true/false, never 0/1. Reply with a JSON object {"inputs": [...]} holding the values in the
order the program consumes them, and nothing else."""

_TASK = """Program:
```python
{source}
```
Make `{function}` raise at `{expression}`.
Hypothesis: {trigger}"""


def llm_input_check(result: dict, *, llm, work_dir: Path, rounds: int = 3) -> dict:
    """``llm`` is an LLMClient; skipped when an earlier arm already found a crashing input."""
    if any(s.get("verdict") == FUZZ_FOUND for s in result.get("steps") or []):
        return {"verdict": FUZZ_FOUND, "reason": "input already found by the search", "skipped": True}
    path = replay_program_path(result) if result.get("program_path") else None
    hypothesis = result["hypothesis"]
    program = None if path is None else program_for_result(path, hypothesis)
    if program is None:
        return {"verdict": LLM_INPUT_UNAVAILABLE, "reason": "no replay program for the hypothesis"}
    function = hypothesis["function"].split(".")[-1]
    task = _TASK.format(source=program.source, function=hypothesis["function"],
                        expression=hypothesis["suspect_expression"],
                        trigger=hypothesis.get("trigger_condition") or "not given")
    case_dir = Path(work_dir) / str(hypothesis.get("hypothesis_id", "case"))
    case_dir.mkdir(parents=True, exist_ok=True)
    feedback, tried = "", []
    for _ in range(rounds):
        reply = llm.complete(_SYSTEM, task + feedback, json_mode=True)
        usage = reply.telemetry or {}
        with (case_dir / "llm_usage.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"model": reply.model, "prompt_tokens": usage.get("prompt_tokens"),
                                  "completion_tokens": usage.get("completion_tokens")}) + "\n")
        try:
            inputs = json.loads(reply.harness)["inputs"]
        except (ValueError, KeyError, TypeError):
            feedback = '\n\nYour last reply was not {"inputs": [...]}.'
            continue
        if not isinstance(inputs, list):
            feedback = '\n\n"inputs" must be a list.'
            continue
        replay = concrete_replay(program, function, inputs=inputs)
        tried.append({"inputs": inputs, "replay": replay.to_dict()})
        if replay.status == "reproduced":
            return {"verdict": FUZZ_FOUND, "reason": "LLM-proposed input", "replay": replay.to_dict(),
                    "tried": tried}
        outcome = {"other_failure": f"it raised {replay.exception_type} at line {replay.line}, not at the "
                                    "suspect expression",
                   "not_reproduced": "the program ran without raising",
                   }.get(replay.status, f"the replay could not use it: {replay.reason}")
        feedback = f"\n\nYou proposed {json.dumps(inputs)}; {outcome}. Propose another sequence."
    return {"verdict": LLM_INPUT_NOTHING, "reason": f"no proposal crashed in {rounds} rounds", "tried": tried}
