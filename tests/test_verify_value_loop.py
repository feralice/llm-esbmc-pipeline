import json
from dataclasses import dataclass, field
from pathlib import Path

import main
from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify import esbmc_run, loop
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.outcome import (
    PROPERTY_REJECTED,
    VALUE_CONFIRMED,
    VALUE_VIOLATION,
)

SOURCE = "def magnitude(x):\n    return x if x > 0 else x\n"
FIXED = "def magnitude(x):\n    # FIXED_ONLY_MARKER\n    return x if x > 0 else -x\n"
GOOD = json.dumps({"params": {"x": "int"}, "returns": "int", "postcondition": "result >= 0"})


@dataclass
class FakeLLM:
    replies: list[str]
    model: str = "fake"
    systems: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        self.systems.append(system_prompt)
        self.prompts.append(user_prompt)
        return SynthResult(harness=self.replies.pop(0), raw_response="", model=self.model,
                           telemetry={"total_tokens": 10})


def _esbmc_hits_the_assert(path, **_):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    line = next((n for n, text in enumerate(lines, 1) if text.strip().startswith("assert ")), 0)
    return ESBMCDirectResult(source_file=str(path), status="violation_found", command=["esbmc"], returncode=1,
                             summary="violation_found",
                             details={"violated_properties": ["assertion"], "violated_files": [""],
                                      "violated_property_records": [{"kind": "assertion", "line": line}]})


def _run(work_dir, monkeypatch, llm, fixed=FIXED, oracle=VALUE_ORACLE):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc_hits_the_assert)
    monkeypatch.setattr(loop, "convert", lambda source, command: "")
    h = BugHypothesis("m.py", "magnitude", "x if x > 0 else x", oracle=oracle)
    return loop.verify_hypothesis(h, llm=llm, source=SOURCE, esbmc_command=["esbmc"], bound=5,
                                  timeout_seconds=30, work_dir=work_dir, fixed_source=fixed)


def test_a_wrong_value_is_confirmed_when_the_fixed_version_keeps_the_property(tmp_path, monkeypatch):
    result = _run(tmp_path, monkeypatch, FakeLLM([GOOD]))
    assert result.verdict == VALUE_CONFIRMED
    assert result.replay["status"] == "property_violated" and result.replay["inputs"] == [-1]
    assert result.control["status"] == "not_reproduced"


def test_a_property_the_fixed_version_also_breaks_is_rejected(tmp_path, monkeypatch):
    wrong = json.dumps({"params": {"x": "int"}, "returns": "int", "postcondition": "result > 0"})
    assert _run(tmp_path, monkeypatch, FakeLLM([wrong])).verdict == PROPERTY_REJECTED


def test_without_a_fixed_version_the_violation_is_not_confirmed(tmp_path, monkeypatch):
    result = _run(tmp_path, monkeypatch, FakeLLM([GOOD]), fixed=None)
    assert result.verdict == VALUE_VIOLATION and "control" not in result.to_dict()


def test_a_missing_postcondition_goes_back_to_the_llm(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"x": "int"}, "returns": "int"}), GOOD])
    result = _run(tmp_path, monkeypatch, llm)
    assert "postcondition: missing" in llm.prompts[1]
    assert result.verdict == VALUE_CONFIRMED


def test_the_fixed_version_never_reaches_the_llm(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"x": "int"}}), GOOD])
    _run(tmp_path, monkeypatch, llm)
    assert len(llm.prompts) == 2
    assert all("FIXED_ONLY_MARKER" not in text and "else -x" not in text for text in [*llm.prompts, *llm.systems])


def test_the_value_prompt_is_only_for_value_hypotheses(tmp_path, monkeypatch):
    value = FakeLLM([GOOD])
    _run(tmp_path / "value", monkeypatch, value)
    assert value.systems[0].startswith(loop.SYSTEM_PROMPT) and "postcondition" in value.systems[0]
    assert "Kind: wrong result" in value.prompts[0]
    exception = FakeLLM([json.dumps({"params": {"x": "int"}})])
    _run(tmp_path / "exception", monkeypatch, exception, oracle="")
    assert exception.systems[0] == loop.SYSTEM_PROMPT and "Kind: wrong result" not in exception.prompts[0]


def test_run_verify_hands_the_fixed_file_only_to_value_hypotheses(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text(SOURCE, encoding="utf-8")
    fixed_dir = tmp_path / "fixed"
    fixed_dir.mkdir()
    (fixed_dir / "m.py").write_text(FIXED, encoding="utf-8")
    seen = {}

    def fake_verify(h, **kwargs):
        seen[h.oracle] = kwargs["fixed_source"]
        return loop.VerifyResult(h, "NOT_CONFIRMED")

    monkeypatch.setattr(loop, "verify_hypothesis", fake_verify)
    hypotheses = [BugHypothesis(str(tmp_path / "m.py"), "magnitude", "x if x > 0 else x", oracle=oracle)
                  for oracle in (VALUE_ORACLE, "")]
    loop.run_verify(hypotheses, llm=None, output_dir=tmp_path / "out", fixed_sources=fixed_dir)
    assert seen == {VALUE_ORACLE: FIXED, "": None}


class _Synthesizer:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]


class _Nothing:
    def analyze(self, unit):
        return []


def test_main_passes_the_fixed_sources_to_verify(tmp_path, monkeypatch):
    source = tmp_path / "m.py"
    source.write_text(SOURCE, encoding="utf-8")
    captured = {}

    def fake_verify(hypotheses, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Nothing())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", fake_verify)
    args = main.build_parser().parse_args(["--mode", "hybrid", "--input", str(source), "--output-dir",
                                           str(tmp_path / "out"), "--fixed-sources", str(tmp_path / "fixed")])
    assert main.mode_v2(args) == 0
    assert captured["fixed_sources"] == tmp_path / "fixed"


def test_a_constructor_value_hypothesis_is_unsupported_before_any_llm_call(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "convert", lambda source, command: "")
    source = "class C:\n    def __init__(self, x):\n        self.x = x - 1\n"
    llm = FakeLLM([GOOD])
    h = BugHypothesis("m.py", "C.__init__", "x - 1", oracle=VALUE_ORACLE)
    result = loop.verify_hypothesis(h, llm=llm, source=source, esbmc_command=None, bound=5, timeout_seconds=30,
                                    work_dir=tmp_path)
    assert result.verdict == "UNSUPPORTED" and "constructor" in result.reason and llm.prompts == []


def test_the_value_prompt_says_which_receiver_attributes_the_postcondition_may_read():
    # spec_problems accepts only the receiver attributes the function reads.
    assert "self.<attribute> the function reads" in loop.VALUE_PROMPT


def test_main_refuses_fixed_sources_that_also_feed_a_prompt(tmp_path, monkeypatch):
    source = tmp_path / "m.py"
    source.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(main, "run_verify", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    for flag in ("--verification-sources", "--context-sources"):
        args = main.build_parser().parse_args(["--mode", "hybrid", "--input", str(source), "--output-dir",
                                               str(tmp_path / "out"), "--fixed-sources", str(tmp_path),
                                               flag, str(tmp_path) + "/"])
        assert main.mode_v2(args) == 1
