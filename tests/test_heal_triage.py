
from research_pipeline.verify import healing, loop
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.outcome import CONFIRMED, UNSUPPORTED


class _Healer:
    proposals = 0

    def refresh(self):
        return "v1"

    def propose(self, *args, **kwargs):
        type(self).proposals += 1
        return None

    def learn(self, *args, **kwargs):
        return 0


def _run(monkeypatch, tmp_path, verdict, triage):
    monkeypatch.setattr(healing, "verify_hypothesis",
                        lambda h, **kwargs: loop.VerifyResult(h, verdict, "ERROR: NameError: name 'IOError' is not defined"))
    _Healer.proposals = 0
    h = BugHypothesis(str(tmp_path / "m.py"), "f", "1 // a", category="division_by_zero")
    return healing.verify_with_healing(h, healer=_Healer(), source="def f(a):\n    return 1 // a\n", triage=triage,
                                       work_dir=tmp_path, llm=None)


def test_triage_skips_repair_for_unsupported(tmp_path, monkeypatch):
    _run(monkeypatch, tmp_path, UNSUPPORTED, triage=True)
    assert _Healer.proposals == 0


def test_without_triage_unsupported_is_repaired(tmp_path, monkeypatch):
    _run(monkeypatch, tmp_path, UNSUPPORTED, triage=False)
    assert _Healer.proposals > 0


def test_triage_never_touches_other_verdicts(tmp_path, monkeypatch):
    result = _run(monkeypatch, tmp_path, CONFIRMED, triage=True)
    assert result.verdict == CONFIRMED and _Healer.proposals == 0
