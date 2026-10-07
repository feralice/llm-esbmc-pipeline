"""Dynamic arm: search the generated program under CPython when ESBMC gave no verdict.

Evidence only: a crash found here is never a formal confirmation."""

from __future__ import annotations

from .replay import concrete_replay
from .validation import program_for_result, replay_program_path

FUZZ_FOUND = "FUZZ_FOUND"
FUZZ_OTHER = "FUZZ_OTHER"
FUZZ_NOTHING = "FUZZ_NOTHING"
FUZZ_UNAVAILABLE = "FUZZ_UNAVAILABLE"

_BY_STATUS = {"reproduced": FUZZ_FOUND, "other_failure": FUZZ_OTHER, "not_reproduced": FUZZ_NOTHING}


def dynamic_check(result: dict, *, random_runs: int = 300, timeout_seconds: int = 60, seed: int = 0) -> dict:
    if not result.get("program_path"):
        return {"verdict": FUZZ_UNAVAILABLE, "reason": "no generated program", "replay": {}}
    path = replay_program_path(result)
    program = None if path is None else program_for_result(path, result["hypothesis"])
    if program is None:
        return {"verdict": FUZZ_UNAVAILABLE, "reason": "hypothesis not found in the pre-rewrite program", "replay": {}}
    replay = concrete_replay(program, result["hypothesis"]["function"].split(".")[-1], random_runs=random_runs,
                             timeout_seconds=timeout_seconds, seed=seed)
    return {"verdict": _BY_STATUS.get(replay.status, FUZZ_UNAVAILABLE), "reason": replay.reason,
            "replay": replay.to_dict()}
