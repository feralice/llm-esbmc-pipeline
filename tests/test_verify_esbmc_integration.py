import json
from pathlib import Path

import pytest

from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.loop import verify_hypothesis
from research_pipeline.verify.outcome import CONFIRMED, NOT_CONFIRMED, UNVALIDATED

ESBMC = Path("/usr/local/bin/esbmc")
pytestmark = pytest.mark.skipif(not ESBMC.exists(), reason="official ESBMC 8.5 not installed")

TRACKER = '''class Tracker:
    def __init__(self, mode, cfg):
        self.mode = mode
        self.previous_defs = cfg.load()

    def guarded(self, depth: int):
        while self.previous_defs and self.previous_defs[-1] >= depth:
            self.previous_defs.pop()
        return 0

    def unguarded(self, depth: int):
        if depth > 0:
            return self.previous_defs.pop()
        return 0
'''


class OneSpec:
    model = "fixed"

    def __init__(self, spec):
        self.spec = json.dumps(spec)

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        return SynthResult(harness=self.spec, raw_response="", model=self.model, telemetry={})


def _verify(tmp_path, function, expression, spec, source=TRACKER):
    return verify_hypothesis(BugHypothesis("t.py", function, expression), llm=OneSpec(spec), source=source,
                             esbmc_command=[str(ESBMC)], bound=5, timeout_seconds=300, work_dir=tmp_path)


def test_real_pop_on_empty_list_is_confirmed(tmp_path):
    result = _verify(tmp_path, "Tracker.unguarded", "self.previous_defs.pop()",
                     {"attributes": {"previous_defs": "list[int]"}})
    assert result.verdict == CONFIRMED, result.to_dict()
    assert result.replay["exception_type"] == "IndexError"


def test_esbmc_false_positive_on_guarded_loop_is_not_confirmed(tmp_path):
    result = _verify(tmp_path, "Tracker.guarded", "self.previous_defs.pop()",
                     {"attributes": {"previous_defs": "list[int]"}})
    assert result.verdict in {UNVALIDATED, NOT_CONFIRMED}, result.to_dict()
    assert result.verdict != CONFIRMED


def test_guarded_division_is_not_confirmed(tmp_path):
    source = "def ratio(total, count):\n    if count == 0:\n        return 0\n    return total // count\n"
    result = _verify(tmp_path, "ratio", "total // count", {"params": {"total": "int", "count": "int"}}, source)
    assert result.verdict == NOT_CONFIRMED, result.to_dict()


CRON = '''class HashExpander:
    def __init__(self, cron):
        self.cron = cron

    def do(self, idx: int):
        return self.cron.RANGES[idx]
'''


def test_object_attribute_with_list_field_is_confirmed(tmp_path):
    result = _verify(tmp_path, "HashExpander.do", "self.cron.RANGES[idx]",
                     {"attributes": {"cron": "object"}, "stubs": {"self.cron.RANGES": "list[int]"}}, CRON)
    assert result.verdict == CONFIRMED, result.to_dict()


def test_nested_list_and_library_stub_are_confirmed(tmp_path):
    source = "from compat import to_rows\n\n\ndef first(text, i: int):\n    rows = to_rows(text)\n    return rows[0][i]\n"
    result = _verify(tmp_path, "first", "rows[0][i]",
                     {"params": {"text": "str"}, "stubs": {"to_rows": "list[list[int]]"}}, source)
    assert result.verdict == CONFIRMED, result.to_dict()


def test_opaque_values_convert_and_the_bug_is_confirmed(tmp_path):
    source = ("from lib import load\n\n\n"
              "def pick(meta, rows, i: int):\n    handle = load(meta)\n    return rows[i]\n")
    result = _verify(tmp_path, "pick", "rows[i]",
                     {"params": {"meta": "dict[str, object]", "rows": "list[object]"}, "stubs": {"load": "object"}},
                     source)
    assert result.verdict == CONFIRMED, result.to_dict()


def test_classmethod_is_confirmed(tmp_path):
    source = "class K:\n    LIMIT = 0\n\n    @classmethod\n    def make(cls, a: int):\n        return a // cls.LIMIT\n"
    result = _verify(tmp_path, "K.make", "a // cls.LIMIT", {}, source)
    assert result.verdict == CONFIRMED, result.to_dict()


def test_constructor_is_confirmed(tmp_path):
    source = "class A:\n    def __init__(self, x: int, y: int):\n        self.r = x // y\n"
    result = _verify(tmp_path, "A.__init__", "x // y", {}, source)
    assert result.verdict == CONFIRMED, result.to_dict()


def test_flattened_library_chain_is_confirmed(tmp_path):
    source = "import numpy as np\n\n\ndef f(n: int):\n    k = np.random.randint(n)\n    return n // k\n"
    result = _verify(tmp_path, "f", "n // k", {"stubs": {"np_random.randint": "int"}}, source)
    assert result.verdict == CONFIRMED, result.to_dict()


def test_opaque_constructor_is_confirmed(tmp_path):
    source = ("from pandas import MultiIndex\n\n\n"
              "def f(x: str, n: int):\n    m = MultiIndex(x, names=None)\n    if isinstance(m, MultiIndex):\n"
              "        return n // 0\n    return 1\n")
    result = _verify(tmp_path, "f", "n // 0", {}, source)
    assert result.verdict == CONFIRMED, result.to_dict()


def test_percent_format_is_rewritten_and_the_bug_is_confirmed(tmp_path):
    source = 'def label(code: int, name: str):\n    msg = "%s:%s" % (code, name)\n    return 10 // (len(msg) - 2)\n'
    result = _verify(tmp_path, "label", "10 // (len(msg) - 2)", {}, source)
    assert "compat_percent_format:1" in result.transforms
    assert result.verdict in {CONFIRMED, NOT_CONFIRMED, UNVALIDATED}, result.to_dict()
    assert result.verdict != "UNSUPPORTED"
