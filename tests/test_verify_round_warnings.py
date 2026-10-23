import sys

from research_pipeline.verify import round_warnings as rw
from research_pipeline.verify.round_warnings import mypy_new_errors, round_warnings

ORIGINAL = """import collections

class C(collections.OrderedDict):
    def __setitem__(self, k, v):
        if len(self) > 3:
            return
        super().__setitem__(k, v)
"""

EMPTIED = """class Base:
    pass

class C(Base):
    def __setitem__(self, k, v):
        if len(self) > 3:
            return
        super().__setitem__(k, v)
"""


def test_mypy_flags_the_emptied_base_class():
    errors = mypy_new_errors(ORIGINAL, EMPTIED)
    assert any("len" in e for e in errors)
    assert any("__setitem__" in e for e in errors)


def test_identical_programs_have_no_new_errors():
    assert mypy_new_errors(ORIGINAL, ORIGINAL) == []


def test_missing_mypy_is_not_measured(monkeypatch):
    monkeypatch.setattr(rw, "_mypy_command", lambda: [sys.executable, "-c", "import nonexistent_mypy_module"])
    assert mypy_new_errors(ORIGINAL, EMPTIED) is None
    assert "mypy: não medido" in round_warnings(EMPTIED, ORIGINAL, "C.__setitem__")


def test_body_change_is_flagged():
    changed = EMPTIED.replace("> 3", "> 4")
    assert "body_changed" in round_warnings(changed, EMPTIED, "C.__setitem__")
    assert "body_changed" not in round_warnings(EMPTIED, EMPTIED, "C.__setitem__")


def test_mypy_timeout_is_not_measured(monkeypatch):
    monkeypatch.setattr(rw, "_mypy_command", lambda: [sys.executable, "-c", "import time; time.sleep(30)"])
    assert mypy_new_errors(ORIGINAL, EMPTIED, timeout=1) is None
    assert "mypy: não medido" in round_warnings(EMPTIED, ORIGINAL, "C.__setitem__", mypy_timeout=1)


def test_round_warnings_surface_new_mypy_errors():
    warnings = round_warnings(EMPTIED, ORIGINAL, "C.__setitem__")
    assert any(w.startswith("mypy_new:") and "__setitem__" in w for w in warnings)


def test_precomputed_original_messages_skip_the_original_run(monkeypatch):
    messages = rw.mypy_messages(ORIGINAL, 60)
    calls = []
    real = rw.mypy_messages
    monkeypatch.setattr(rw, "mypy_messages", lambda source, timeout: calls.append(source) or real(source, timeout))
    assert any("len" in e for e in mypy_new_errors(ORIGINAL, EMPTIED, original_messages=messages))
    assert calls == [EMPTIED]
