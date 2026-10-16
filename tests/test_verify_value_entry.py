import hashlib
from pathlib import Path

import main
from research_pipeline.llm.findings import finding_from_dict
from research_pipeline.llm.prompt_variants import apply_variants
from research_pipeline.llm.prompts import load_system_prompt
from research_pipeline.llm.schema import v2_findings_schema
from research_pipeline.models import Finding
from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis

BASE = load_system_prompt(include_smells=False, v2_detection=True)


def test_exception_hypotheses_keep_their_old_ids():
    h = BugHypothesis("a.py", "f", "x // y", line=3)
    assert h.hypothesis_id == hashlib.sha1(b"a.py|f|3|x // y").hexdigest()[:12]


def test_a_value_hypothesis_gets_its_own_id_and_round_trips():
    h = BugHypothesis("a.py", "f", "x // y", line=3, oracle=VALUE_ORACLE)
    assert h.hypothesis_id != BugHypothesis("a.py", "f", "x // y", line=3).hypothesis_id
    data = h.to_dict()
    assert data["oracle"] == "value"
    assert BugHypothesis(**{k: v for k, v in data.items() if k != "hypothesis_id"}) == h


def test_candidates_carry_the_oracle_to_the_hypothesis():
    assert Candidate.from_dict({"file": "a.py", "function": "f"}).oracle == ""
    candidate = Candidate.from_dict({"file": "a.py", "function": "f", "expression": "x", "oracle": "value"})
    assert candidate.to_dict()["oracle"] == "value"
    assert BugHypothesis.from_candidate(candidate).oracle == VALUE_ORACLE


def test_a15_asks_how_the_bug_shows_in_prompt_and_schema():
    changed = apply_variants(BASE, ("A15",))
    assert "## BUG DE RESULTADO ERRADO" in changed and '"failure_mode"' in changed
    metadata = v2_findings_schema(("A15",))["schema"]["properties"]["findings"]["items"]["properties"]["metadata"]
    assert metadata["properties"]["failure_mode"]["enum"] == ["excecao", "resultado_errado", "outro"]
    assert "failure_mode" in metadata["required"]
    assert "failure_mode" not in v2_findings_schema(())["schema"]["properties"]["findings"]["items"][
        "properties"]["metadata"]["properties"]


def test_failure_mode_is_read_from_the_metadata():
    raw = {"metadata": {"expression": "x", "failure_mode": "resultado_errado"}, "verifiable": False}
    assert finding_from_dict(raw).metadata["failure_mode"] == "resultado_errado"


class _Synthesizer:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]


class _WrongResultAnalyzer:
    def __init__(self, failure_mode):
        self.failure_mode = failure_mode

    def analyze(self, unit):
        return [Finding(id="w", stage="llm_analysis", finding_type="suspected_bug", category="", title="",
                        explanation="returns x for a negative x", evidence=[], verifiable=False,
                        confidence="high",
                        metadata={"expression": "x if x > 0 else x", "failure_mode": self.failure_mode})]


def _detected(tmp_path: Path, monkeypatch, failure_mode: str, variants: str) -> list:
    # One directory per run: a shared output directory would resume the previous run's checkpoint.
    work = tmp_path / f"{failure_mode}-{variants or 'base'}"
    work.mkdir()
    source = work / "m.py"
    source.write_text("def magnitude(x):\n    return x if x > 0 else x\n", encoding="utf-8")
    captured = {}

    def fake_verify(hypotheses, **kwargs):
        captured["hypotheses"] = hypotheses
        return []

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _WrongResultAnalyzer(failure_mode))
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", fake_verify)
    argv = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(work / "out")]
    if variants:
        argv += ["--v2-variants", variants]
    assert main.mode_v2(main.build_parser().parse_args(argv)) == 0
    return captured["hypotheses"]


def test_with_a15_a_wrong_result_finding_becomes_a_value_hypothesis(tmp_path, monkeypatch):
    hypotheses = _detected(tmp_path, monkeypatch, "resultado_errado", "A15")
    assert [(h.function, h.oracle) for h in hypotheses] == [("magnitude", VALUE_ORACLE)]


def test_without_a15_a_wrong_result_finding_is_still_held(tmp_path, monkeypatch):
    assert _detected(tmp_path, monkeypatch, "resultado_errado", "") == []
    assert _detected(tmp_path, monkeypatch, "outro", "A15") == []


def test_a15_composes_with_the_other_variants():
    changed = apply_variants(BASE, ("A1", "A2", "A9", "A13", "A14", "A15"))
    assert "## BUG DE RESULTADO ERRADO" in changed and '"quoted_line"' in changed and '"failure_mode"' in changed
    metadata = v2_findings_schema(("A9", "A14", "A15"))["schema"]["properties"]["findings"]["items"][
        "properties"]["metadata"]
    assert {"crash_expression", "quoted_line", "trigger", "failure_mode"} <= set(metadata["required"])


def test_a15_changes_the_fingerprint_of_the_detection_prompt():
    # A checkpoint of a run without A15 must not resume a run with it.
    assert "detector_system_prompt" in main._v2_fingerprint({"v2_variants": ["A15"]}, [])


def test_a15_fingerprints_the_value_property_prompt():
    assert "value_prompt" in main._v2_fingerprint({"v2_variants": ["A15"]}, [])
    assert "value_prompt" not in main._v2_fingerprint({"v2_variants": []}, [])
