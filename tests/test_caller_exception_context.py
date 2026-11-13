from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.caller_facts import caught_by_callers
from research_pipeline.verify.outcome import CONFIRMED, HANDLED_BY_CALLER, handles, final_verdict
from research_pipeline.verify.outcome import EsbmcReading
from research_pipeline.verify.replay import ReplayVerdict

GUARDED = """
def parse(text):
    return int(text)

def read(line):
    try:
        return parse(line)
    except ValueError:
        return None
"""

UNGUARDED = """
def parse(text):
    return int(text)

def read(line):
    return parse(line)
"""

TWO_SITES = GUARDED + """
def other(line):
    return parse(line)
"""


def _h(path):
    return BugHypothesis(str(path), "parse", "int(text)", category="invalid_precondition")


def _reading():
    return EsbmcReading("violation", "violation", exceptions=("ValueError",))


def _replay():
    return ReplayVerdict("reproduced", exception_type="ValueError")


def test_a_caller_that_catches_the_exception_is_detected(tmp_path):
    path = tmp_path / "m.py"
    path.write_text(GUARDED, encoding="utf-8")
    assert caught_by_callers(_h(path), GUARDED, None) == (frozenset({"ValueError"}),)


def test_an_unguarded_call_site_catches_nothing(tmp_path):
    path = tmp_path / "m.py"
    path.write_text(UNGUARDED, encoding="utf-8")
    assert caught_by_callers(_h(path), UNGUARDED, None) == (frozenset(),)


def test_one_unguarded_site_among_guarded_ones_is_not_enough(tmp_path):
    path = tmp_path / "m.py"
    path.write_text(TWO_SITES, encoding="utf-8")
    caught = caught_by_callers(_h(path), TWO_SITES, None)
    assert len(caught) == 2 and frozenset() in caught
    assert final_verdict(_reading(), _replay(), caught) == CONFIRMED


def test_every_site_catching_the_exception_gives_handled_by_caller(tmp_path):
    path = tmp_path / "m.py"
    path.write_text(GUARDED, encoding="utf-8")
    caught = caught_by_callers(_h(path), GUARDED, None)
    assert final_verdict(_reading(), _replay(), caught) == HANDLED_BY_CALLER


def test_no_known_call_site_keeps_the_confirmed_verdict(tmp_path):
    source = "def parse(text):\n    return int(text)\n"
    path = tmp_path / "m.py"
    path.write_text(source, encoding="utf-8")
    assert caught_by_callers(_h(path), source, None) == ()
    assert final_verdict(_reading(), _replay(), ()) == CONFIRMED


def test_handlers_follow_the_exception_hierarchy():
    assert handles("ValueError", frozenset({"Exception"}))
    assert handles("ValueError", frozenset({"BaseException"}))
    assert not handles("ValueError", frozenset({"TypeError"}))
    assert not handles("NotARealError", frozenset({"Exception"}))
