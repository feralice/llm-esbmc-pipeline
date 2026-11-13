from pathlib import Path

from research_pipeline.verify import healing, loop
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.outcome import UNSUPPORTED


class _Healer:
    proposals = 0

    def refresh(self):
        return "v1"

    def propose(self, *args, **kwargs):
        type(self).proposals += 1
        return None

    def learn(self, *args, **kwargs):
        return 0


def _run(monkeypatch, tmp_path, reason):
    monkeypatch.setattr(healing, "verify_hypothesis",
                        lambda h, **kwargs: loop.VerifyResult(h, UNSUPPORTED, reason))
    _Healer.proposals = 0
    h = BugHypothesis(str(tmp_path / "m.py"), "f", "1 // a", category="division_by_zero")
    return healing.verify_with_healing(h, healer=_Healer(), source="def f(a):\n    return 1 // a\n",
                                       work_dir=tmp_path, llm=None)


def test_async_entry_point_is_not_repaired(tmp_path, monkeypatch):
    result = _run(monkeypatch, tmp_path, "UNSUPPORTED: async entry point: async method or nested coroutine")
    assert result.verdict == UNSUPPORTED and _Healer.proposals == 0


def test_numpy_array_parameter_is_not_repaired(tmp_path, monkeypatch):
    _run(monkeypatch, tmp_path, "UNSUPPORTED: TypeError: a list passed where a numpy array parameter is expected")
    assert _Healer.proposals == 0


def test_other_refusals_are_still_repaired(tmp_path, monkeypatch):
    _run(monkeypatch, tmp_path, "UNSUPPORTED: ERROR: Cannot resolve nested attribute: _meta")
    assert _Healer.proposals > 0
