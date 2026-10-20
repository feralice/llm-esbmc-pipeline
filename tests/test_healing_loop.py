from research_pipeline.verify import healing
from research_pipeline.verify.healing import Patch, verify_with_healing
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.loop import VerifyResult
from research_pipeline.verify.outcome import (
    CONFIRMED,
    LLM_ONLY,
    NOT_CONFIRMED,
    UNSUPPORTED,
    VERDICTS,
)

SOURCE = "def f(x):\n    return 1 / x\n"
H = BugHypothesis(file="m.py", function="f", suspect_expression="1 / x")


class ScriptedHealer:
    def __init__(self, patches):
        self.patches, self.calls = list(patches), []

    def propose(self, h, source, verdict, reason, previous):
        self.calls.append((h, source, verdict, list(previous)))
        return self.patches.pop(0) if self.patches else None


def _verify(verdicts, seen):
    def fake(h, *, source, llm, **kwargs):
        seen.append((h, source, llm))
        return VerifyResult(h, verdicts.pop(0), reason=f"reason {len(seen)}")
    return fake


def test_llm_only_is_a_verdict():
    assert LLM_ONLY in VERDICTS


def test_healable_verdict_gets_rounds_then_llm_only(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([UNSUPPORTED] * 4, seen))
    stub = Patch(definitions="def g(a=None) -> int:\n    return nondet_int()\n")
    result = verify_with_healing(H, healer=ScriptedHealer([stub] * 3), source=SOURCE, llm="spec", rounds=3)
    assert result.verdict == LLM_ONLY
    assert result.reason.startswith("UNSUPPORTED: reason 4")
    assert len(seen) == 4 and len(result.healing) == 3


def test_checked_verdict_is_not_healed(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([NOT_CONFIRMED], seen))
    healer = ScriptedHealer([])
    assert verify_with_healing(H, healer=healer, source=SOURCE, llm="spec").verdict == NOT_CONFIRMED
    assert healer.calls == []


def test_repair_that_confirms_keeps_the_original_hypothesis(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([UNSUPPORTED, CONFIRMED], seen))
    moved = Patch(hypothesis_function="f", hypothesis_expression="x")
    result = verify_with_healing(H, healer=ScriptedHealer([moved]), source=SOURCE, llm="spec")
    assert result.verdict == CONFIRMED
    assert result.hypothesis == H
    assert seen[1][0].suspect_expression == "x"
    assert result.healing[0]["hypothesis_after"]["suspect_expression"] == "x"


def test_patched_source_and_new_spec_llm_are_used(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([UNSUPPORTED, NOT_CONFIRMED], seen))
    stub = Patch(definitions="def g(a=None) -> int:\n    return nondet_int()\n")
    verify_with_healing(H, healer=ScriptedHealer([stub]), source=SOURCE, llm="saved", spec_llm_after_heal="live")
    assert seen[0][2] == "saved" and seen[1][2] == "live"
    assert "def g" in seen[1][1] and "def g" not in SOURCE


def test_invalid_patch_spends_a_round(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([UNSUPPORTED], seen))
    bad = Patch(edits=(("return 1 / x", "return 0"),))
    result = verify_with_healing(H, healer=ScriptedHealer([bad, None]), source=SOURCE, llm="spec", rounds=2)
    assert result.verdict == LLM_ONLY and len(seen) == 1
    assert "suspect" in result.healing[0]["problems"][0]
    assert result.healing[1]["problems"] == ["no usable repair"]


def test_without_healer_is_identity(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([UNSUPPORTED], seen))
    result = verify_with_healing(H, healer=None, source=SOURCE, llm="spec")
    assert result.verdict == UNSUPPORTED and result.healing == []


def test_healing_is_in_the_report(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([UNSUPPORTED], seen))
    data = verify_with_healing(H, healer=ScriptedHealer([]), source=SOURCE, llm="spec", rounds=1).to_dict()
    assert data["verdict"] == LLM_ONLY and data["healing"][0]["verdict_before"] == UNSUPPORTED


def test_build_healer_modes(tmp_path):
    from research_pipeline.verify.healing import build_healer
    assert build_healer("none", llm="x", esbmc_command=["esbmc"]) is None
    plain = build_healer("error", llm="x", esbmc_command=["esbmc"])
    assert plain.knowledge is None
    kb = build_healer("error+kb", llm="x", esbmc_command=["/nonexistent/esbmc"], cache_dir=tmp_path)
    assert kb.knowledge is not None and kb.knowledge.tests == []


def test_run_verify_heals_when_given_a_healer(monkeypatch, tmp_path):
    from research_pipeline.verify import loop
    source = tmp_path / "m.py"
    source.write_text(SOURCE, encoding="utf-8")
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _verify([UNSUPPORTED], seen))
    monkeypatch.setattr(loop, "verify_hypothesis", _verify([UNSUPPORTED], seen))
    h = BugHypothesis(file=str(source), function="f", suspect_expression="1 / x")
    rows = loop.run_verify([h], llm="spec", output_dir=tmp_path, healer=ScriptedHealer([]), heal_rounds=1)
    assert rows[0]["verdict"] == LLM_ONLY


BODY = "import os\n\n\ndef f(x):\n    msg = 'bad %r' % x\n    return 1 / x\n"


def test_a_body_simplification_is_replayed_on_the_original_body(monkeypatch):
    seen, replays = [], []

    def fake(h, *, source, llm, replay_source=None, **kwargs):
        seen.append(source)
        replays.append(replay_source)
        return VerifyResult(h, UNSUPPORTED if len(seen) == 1 else CONFIRMED)
    monkeypatch.setattr(healing, "verify_hypothesis", fake)
    simplify = Patch(edits=(("'bad %r' % x", "'bad %s' % x"), ("import os\n", "")))
    h = BugHypothesis(file="m.py", function="f", suspect_expression="1 / x")
    result = verify_with_healing(h, healer=ScriptedHealer([simplify]), source=BODY, llm="spec")
    assert result.verdict == CONFIRMED
    assert "%s" in seen[1] and "import os" not in seen[1]
    assert "%r" in replays[1] and "import os" not in replays[1]
    assert result.healing[0]["simplified_body"] is True


def test_the_replay_program_carries_the_original_body():
    from research_pipeline.verify.grounding import ground
    from research_pipeline.verify.loop import with_original_replay
    from research_pipeline.verify.render import render_program
    from research_pipeline.verify.spec import InputSpec
    simplified = BODY.replace("%r", "%s")
    h = BugHypothesis(file="m.py", function="f", suspect_expression="1 / x")
    spec = InputSpec({"x": "int"}, {}, ())
    program = render_program(ground(h, simplified), spec)
    replayed = with_original_replay(program, h, BODY, spec)
    assert "%r" not in replayed.source
    assert "%r" in replayed.replay_source
    lines = replayed.replay_source.splitlines()
    assert any("1 / x" in lines[a - 1] for a, _ in replayed.replay_target_spans)


def test_an_original_body_that_cannot_be_rebuilt_gives_no_replay():
    from research_pipeline.verify.grounding import ground
    from research_pipeline.verify.loop import with_original_replay
    from research_pipeline.verify.render import render_program
    from research_pipeline.verify.spec import InputSpec
    h = BugHypothesis(file="m.py", function="f", suspect_expression="1 / x")
    spec = InputSpec({"x": "int"}, {}, ())
    program = render_program(ground(h, BODY.replace("%r", "%s")), spec)
    assert isinstance(with_original_replay(program, h, "def g(:\n", spec), str)


def _reasons(verdicts_and_reasons, seen):
    def fake(h, *, source, llm, **kwargs):
        seen.append(source)
        verdict, reason = verdicts_and_reasons.pop(0)
        return VerifyResult(h, verdict, reason=reason)
    return fake


STUB = Patch(definitions="def g(a=None) -> int:\n    return nondet_int()\n")


def test_an_internal_esbmc_error_stops_healing_as_a_tool_bug(monkeypatch):
    from research_pipeline.verify.outcome import ESBMC_ERROR
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _reasons(
        [(UNSUPPORTED, "ERROR: Variable 'kwargs' is not defined"),
         (UNSUPPORTED, "ERROR: vector::_M_range_check: __n (which is 0) >= this->size()")], seen))
    result = verify_with_healing(H, healer=ScriptedHealer([STUB] * 5), source=SOURCE, llm="spec")
    assert result.verdict == ESBMC_ERROR and "internal" in result.reason
    assert len(seen) == 2


def test_a_new_obstacle_resets_the_rounds(monkeypatch):
    seen = []
    chain = [(UNSUPPORTED, f"ERROR: obstacle {n}") for n in "abcd"] + [(NOT_CONFIRMED, "")]
    monkeypatch.setattr(healing, "verify_hypothesis", _reasons(chain, seen))
    result = verify_with_healing(H, healer=ScriptedHealer([STUB] * 9), source=SOURCE, llm="spec", rounds=2)
    assert result.verdict == NOT_CONFIRMED and len(seen) == 5


def test_the_same_obstacle_gets_only_its_rounds(monkeypatch):
    seen = []
    monkeypatch.setattr(healing, "verify_hypothesis", _reasons([(UNSUPPORTED, "ERROR: same at line 3")] * 9, seen))
    result = verify_with_healing(H, healer=ScriptedHealer([STUB] * 9), source=SOURCE, llm="spec", rounds=2)
    assert result.verdict == LLM_ONLY and len(seen) == 3
