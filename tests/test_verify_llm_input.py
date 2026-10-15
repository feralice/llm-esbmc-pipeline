import json
from pathlib import Path

from research_pipeline.verify.dynamic import FUZZ_FOUND
from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.llm_input import LLM_INPUT_NOTHING, llm_input_check
from research_pipeline.verify.pinned import _found_inputs

# The search's small domains never reach x == 100.
PROGRAM = "def f(x: int) -> int:\n    return 10 // (x - 100)\n\n\nf(nondet_int())\n"


class _LLM:
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, user, *, json_mode=False):
        self.prompts.append(user)
        return SynthResult(self.replies.pop(0), "", "fake", {"prompt_tokens": 10, "completion_tokens": 2})


def _result(tmp_path: Path, steps=()) -> dict:
    path = tmp_path / "h_a0.py"
    path.write_text(PROGRAM)
    return {"hypothesis": {"function": "f", "suspect_expression": "10 // (x - 100)", "hypothesis_id": "h"},
            "verdict": "ESBMC_TIMEOUT", "program_path": str(path), "attempts": [{}], "steps": list(steps)}


def test_a_proposal_counts_only_when_the_replay_crashes_with_it(tmp_path):
    llm = _LLM('{"inputs": [3]}', '{"inputs": [100]}')
    outcome = llm_input_check(_result(tmp_path), llm=llm, work_dir=tmp_path / "cases")
    assert outcome["verdict"] == FUZZ_FOUND
    assert outcome["replay"]["inputs"] == [100]
    assert "You proposed [3]; the program ran without raising" in llm.prompts[1]
    assert len((tmp_path / "cases/h/llm_usage.jsonl").read_text().splitlines()) == 2
    assert _found_inputs([{"arm": "llm_input", **outcome}]) == [100]


def test_no_crashing_proposal_in_the_rounds(tmp_path):
    llm = _LLM("not json", json.dumps({"inputs": [1]}))
    outcome = llm_input_check(_result(tmp_path), llm=llm, work_dir=tmp_path / "cases", rounds=2)
    assert outcome["verdict"] == LLM_INPUT_NOTHING


def test_skipped_when_the_search_already_found_an_input(tmp_path):
    found = {"arm": "dynamic", "verdict": FUZZ_FOUND, "replay": {"inputs": [100]}}
    llm = _LLM()
    outcome = llm_input_check(_result(tmp_path, [found]), llm=llm, work_dir=tmp_path)
    assert outcome["skipped"] and not llm.prompts
    assert _found_inputs([found, {"arm": "llm_input", **outcome}]) == [100]
