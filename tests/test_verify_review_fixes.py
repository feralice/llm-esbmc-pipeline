"""Regressions for the whole-branch review findings and for library stubs."""

import ast

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify.grounding import Grounded, GroundingFailure, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.outcome import (
    CONFIRMED, ESBMC_ERROR, UNVALIDATED, EsbmcReading, classify_esbmc, final_verdict,
)
from research_pipeline.verify.render import render_program
from research_pipeline.verify.replay import ReplayVerdict, concrete_replay
from research_pipeline.verify.spec import InputSpec, spec_problems


def _ground(source, function, expression):
    result = ground(BugHypothesis("x.py", function, expression), source)
    assert isinstance(result, Grounded), result
    return result


# C1: ESBMC UNKNOWN / crash is not "safe".
def test_inconclusive_is_an_error_not_safe():
    result = ESBMCDirectResult(source_file="p.py", status="inconclusive", command=["esbmc"], returncode=139,
                               summary="segfault")
    assert classify_esbmc(result).kind == "error"
    assert final_verdict(classify_esbmc(result), ReplayVerdict("reproduced", "TypeError", 2)) == ESBMC_ERROR


# C2: class constants keep their real value.
def test_class_constant_is_not_a_nondet_receiver_attribute():
    source = "class A:\n    SIZE = 4\n\n    def go(self, n: int) -> int:\n        return n // self.SIZE\n"
    grounded = _ground(source, "A.go", "n // self.SIZE")
    assert grounded.receiver_attrs == ()
    program = render_program(grounded, InputSpec({}, {}, ()))
    assert "    SIZE = 4\n" in program.source


def test_declared_class_annotation_without_value_is_still_an_attribute():
    source = "class A:\n    size: int\n\n    def go(self, n: int) -> int:\n        return n // self.size\n"
    assert _ground(source, "A.go", "n // self.size").receiver_attrs == ("size",)


def test_inherited_member_read_is_unsupported():
    source = ("class Base:\n    def helper(self):\n        return 1\n\n\n"
              "class A(Base):\n    def go(self, n: int) -> int:\n        return n // self.helper()\n")
    assert "inherited" in _ground(source, "A.go", "n // self.helper()").unsupported


# I1: a dunder target would be replaced by the shell.


# I2: ESBMC and the replay must see the same exception.
@pytest.mark.parametrize(
    ("kinds", "replayed", "verdict"),
    [
        (["uncaught exception: ZeroDivisionError"], "ZeroDivisionError", CONFIRMED),
        (["IndexError: pop from empty list"], "ZeroDivisionError", UNVALIDATED),
        (["IndexError: pop from empty list"], "IndexError", CONFIRMED),
        (["dereference failure: NULL pointer"], "AttributeError", CONFIRMED),
        (["dereference failure: invalid pointer"], "IndexError", UNVALIDATED),
    ],
)
def test_confirmation_requires_matching_exception(kinds, replayed, verdict):
    reading = classify_esbmc(ESBMCDirectResult(
        source_file="p.py", status="violation_found", command=["esbmc"], returncode=1, summary="",
        details={"violated_properties": kinds, "violated_files": [""] * len(kinds)}))
    assert final_verdict(reading, ReplayVerdict("reproduced", replayed, 3)) == verdict


def test_assumptions_cannot_divide():
    grounded = _ground("def f(a, b):\n    return 1 // b\n", "f", "1 // b")
    problems = spec_problems(InputSpec({"a": "int", "b": "int"}, {}, ("a % b == 0",)), grounded)
    assert problems


def test_self_is_not_an_input_of_a_plain_function():
    grounded = _ground("def f(a):\n    return 1 // a\n", "f", "1 // a")
    assert spec_problems(InputSpec({"a": "int"}, {}, ("self > 0",)), grounded)


# I3: a same-named method of another class raising is not the target.
def test_frame_match_uses_the_target_line_range():
    source = '''class B:
    def run(self, n):
        return [][0]


class A:
    def __init__(self) -> None:
        pass

    def run(self, n):
        return B().run(n)


def _esbmc_main() -> None:
    n: int = nondet_int()
    A().run(n)


_esbmc_main()
'''
    grounded = _ground(source, "A.run", "B().run(n)")
    program = render_program(grounded, InputSpec({"n": "int"}, {}, ()))
    assert concrete_replay(program, "run").status == "reproduced"


# Driver name cannot collide with a target called main.
def test_target_named_main_is_supported():
    grounded = _ground("def main(a):\n    return 1 // a\n", "main", "1 // a")
    program = render_program(grounded, InputSpec({"a": "int"}, {}, ()))
    assert "def _esbmc_main() -> None:" in program.source
    assert concrete_replay(program, "main").status == "reproduced"


def test_async_target_is_unsupported_not_a_hallucination():
    result = ground(BugHypothesis("x.py", "f", "1 // a"), "async def f(a):\n    return 1 // a\n")
    assert isinstance(result, GroundingFailure) and result.unsupported


# Library stubs.
LIB = '''import math
from compat import to_bytes, CompatError
import numpy as np
from helpers import unused_thing


def target(text, n):
    k = to_bytes(text, encoding="utf8")
    m = np.count(text)
    if n < 0:
        raise CompatError("neg")
    return n // (k - m) + math.floor(1.5)
'''


def test_unmodeled_imports_become_declared_stubs():
    grounded = _ground(LIB, "target", "n // (k - m)")
    assert grounded.stub_keys == ("np.count", "to_bytes")
    assert "from compat import" not in grounded.module and "import numpy" not in grounded.module
    assert "import math" in grounded.module
    assert "unused_thing" not in grounded.module
    assert any(t.startswith("stubbed_imports:") for t in grounded.transforms)
    spec = InputSpec({"text": "str", "n": "int"}, {}, (), {"to_bytes": "int", "np.count": "int"})
    program = render_program(grounded, spec)
    tree = ast.parse(program.source)
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert {"to_bytes", "np", "CompatError", "target"} <= names
    assert "def to_bytes(a0, encoding=None) -> int:" in program.source
    assert "class CompatError(Exception):" in program.source
    assert concrete_replay(program, "target").status == "reproduced"


def test_missing_stub_type_is_a_spec_problem():
    grounded = _ground(LIB, "target", "n // (k - m)")
    problems = spec_problems(InputSpec({"text": "str", "n": "int"}, {}, ()), grounded)
    assert "stub 'to_bytes': missing return type" in problems


def test_external_base_class_becomes_an_opaque_stub():
    source = "from lib import Base\n\n\nclass A(Base):\n    def go(self, n: int):\n        return 1 // n\n"
    grounded = _ground(source, "A.go", "1 // n")
    assert grounded.unsupported == "" and grounded.externals.classes == {"Base"}


def test_pruned_methods_imports_are_dropped():
    source = ("import json\nfrom lib import heavy\n\n\nclass A:\n    def __init__(self, cfg):\n        self.cfg = heavy(cfg)\n\n"
              "    def unused(self):\n        return json.dumps(self.cfg)\n\n"
              "    def go(self, n: int):\n        return 1 // n\n")
    grounded = _ground(source, "A.go", "1 // n")
    assert "json" not in grounded.module and "heavy" not in grounded.module
    assert grounded.stub_keys == ()


VALUES = '''import six
from compat import compat_os_name, StringMethods, Base, ScrapyDeprecationWarning
import warnings


class Holder(Base):
    def go(self, x, n):
        if isinstance(x, StringMethods) or compat_os_name == "nt":
            warnings.warn("old", category=ScrapyDeprecationWarning)
        return n // six.PY3
'''


def test_external_values_classes_and_warnings_get_stubs():
    grounded = _ground(VALUES, "Holder.go", "n // six.PY3")
    assert grounded.unsupported == ""
    assert grounded.stub_keys == ("compat_os_name", "six.PY3", "warnings.warn")
    spec = InputSpec({"x": "str", "n": "int"}, {}, (),
                     {"compat_os_name": "str", "six.PY3": "int", "warnings.warn": "None"})
    program = render_program(grounded, spec)
    assert "class StringMethods:\n    pass" in program.source
    assert "class Base:\n    pass" in program.source
    assert "class ScrapyDeprecationWarning(Exception):" in program.source
    assert "compat_os_name: str = nondet_str()" in program.source
    assert "class six:\n    PY3: int = nondet_int()" in program.source
    assert concrete_replay(program, "go").status == "reproduced"


def test_external_decorator_is_still_unsupported():
    source = "from lib import deco\n\n\nclass A:\n    @deco\n    def helper(self):\n        return 1\n\n    def go(self, n: int):\n        return self.helper() // n\n"
    assert "deco" in _ground(source, "A.go", "self.helper() // n").unsupported


def test_dunder_other_than_init_can_be_a_target():
    source = "class A:\n    def __init__(self, xs):\n        self.xs = xs\n\n    def __getitem__(self, i: int):\n        return self.xs[i]\n"
    assert _ground(source, "A.__getitem__", "self.xs[i]").unsupported == ""


# Richer input types (probed on ESBMC 8.5 on 2026-09-29: nested list, dict, bytes, object all convert).
def test_nested_list_dict_and_bytes_render_and_replay():
    source = "def pick(rows, table, raw, i: int, k: str):\n    return rows[0][i] + table[k] + raw[i]\n"
    grounded = _ground(source, "pick", "rows[0][i]")
    spec = InputSpec({"rows": "list[list[int]]", "table": "dict[str, int]", "raw": "bytes"}, {}, ())
    program = render_program(grounded, spec)
    ast.parse(program.source)
    assert "rows: list[list[int]] = []" in program.source
    assert "table: dict[str, int] = {}" in program.source
    assert 'raw: bytes = b"ab"' in program.source
    assert concrete_replay(program, "pick").status == "reproduced"


CRON = '''class HashExpander:
    def __init__(self, cron):
        self.cron = cron

    def do(self, idx: int, text):
        size = len(self.cron.RANGES)
        return self.cron.RANGES[idx] + text.count(self.cron.label()) // size
'''


def test_object_inputs_collect_members_and_become_generated_classes():
    grounded = _ground(CRON, "HashExpander.do", "self.cron.RANGES[idx]")
    assert set(grounded.object_members["self.cron"]) == {"RANGES", "label"}
    assert grounded.object_members["self.cron"]["RANGES"] is None
    assert set(grounded.object_members["text"]) == {"count"}
    spec = InputSpec({"text": "object"}, {"cron": "object"}, (),
                     {"self.cron.RANGES": "list[int]", "self.cron.label": "str", "text.count": "int"})
    assert spec_problems(spec, grounded) == []
    program = render_program(grounded, spec)
    ast.parse(program.source)
    assert "class _Obj_self_cron:" in program.source and "class _Obj_text:" in program.source
    assert "    def label(self) -> str:" in program.source
    assert "self.cron: _Obj_self_cron = _attr_cron" in program.source
    assert concrete_replay(program, "do").status == "reproduced"


def test_object_member_types_are_required_only_when_object_is_chosen():
    grounded = _ground(CRON, "HashExpander.do", "self.cron.RANGES[idx]")
    problems = spec_problems(InputSpec({"text": "str"}, {"cron": "object"}, ()), grounded)
    assert "stub 'self.cron.RANGES': missing return type" in problems
    assert not any("text." in p for p in problems)


def test_tuples_parse_render_and_replay():
    from research_pipeline.verify.spec import TypeShape, parse_type
    assert parse_type("tuple[int, str]") == TypeShape("tuple", items=(TypeShape("int"), TypeShape("str")))
    assert parse_type("tuple[int, list[int]]") is None
    source = "def span(ranges, i: int):\n    lo, hi = ranges[i]\n    return lo // hi\n"
    grounded = _ground(source, "span", "lo // hi")
    program = render_program(grounded, InputSpec({"ranges": "list[tuple[int, int]]"}, {}, ()))
    assert "_v1: tuple[int, int] = (nondet_int(), nondet_int())" in program.source
    assert concrete_replay(program, "span").status == "reproduced"


def test_insisting_on_an_unrepresentable_type_is_unsupported_not_spec_failed(tmp_path, monkeypatch):
    import json

    from research_pipeline.scan.synth import SynthResult
    from research_pipeline.verify import loop
    from research_pipeline.verify.outcome import SPEC_FAILED, UNSUPPORTED

    class Insists:
        model = "fake"

        def __init__(self, reply):
            self.reply = reply

        def complete(self, system_prompt, user_prompt, *, json_mode=False):
            return SynthResult(harness=self.reply, raw_response="", model="fake", telemetry={})

    source = "def f(rows, i: int):\n    return rows[i]\n"
    h = BugHypothesis("f.py", "f", "rows[i]")
    kwargs = dict(source=source, esbmc_command=["esbmc"], bound=5, timeout_seconds=30, work_dir=tmp_path)
    typed = loop.verify_hypothesis(h, llm=Insists(json.dumps({"params": {"rows": "list[Callable[[int], int]]"}})), **kwargs)
    assert typed.verdict == UNSUPPORTED and "outside the supported" in typed.reason
    broken = loop.verify_hypothesis(h, llm=Insists("not json"), **kwargs)
    assert broken.verdict == SPEC_FAILED


def test_duplicate_class_names_use_the_class_that_contains_the_target():
    source = ("class K:\n    def other(self):\n        return 1\n\n\n"
              "class K:\n    def __ne__(self, o):\n        return self.xs[0] != o\n")
    grounded = _ground(source, "K.__ne__", "self.xs[0]")
    assert grounded.receiver_attrs == ("xs",)


def test_internal_error_in_one_hypothesis_does_not_stop_the_run(tmp_path, monkeypatch):
    from research_pipeline.verify import loop
    from research_pipeline.verify.outcome import PIPELINE_ERROR

    (tmp_path / "a.py").write_text("def f(a):\n    return 1 // a\n", encoding="utf-8")

    def boom(*args, **kwargs):
        raise KeyError("__ne__")

    monkeypatch.setattr(loop, "verify_hypothesis", boom)
    hypotheses = [BugHypothesis(str(tmp_path / "a.py"), "f", "1 // a")] * 2
    results = loop.run_verify(hypotheses, llm=None, output_dir=tmp_path)
    assert [r["verdict"] for r in results] == [PIPELINE_ERROR, PIPELINE_ERROR]
    assert "KeyError" in results[0]["reason"]


def test_object_anywhere_is_an_opaque_value():
    from research_pipeline.verify.spec import TypeShape, parse_type
    assert parse_type("dict[str, object]") == TypeShape("dict", TypeShape("object"), key="str")
    assert parse_type("list[Optional[object]]") == TypeShape("list", TypeShape("object", optional=True))
    assert parse_type("Any") == TypeShape("object")
    assert parse_type("tuple[str]") == TypeShape("tuple", items=(TypeShape("str"),))
    source = "from lib import load\n\n\ndef f(meta, i: int):\n    rows = load(meta)\n    return [meta][i]\n"
    grounded = _ground(source, "f", "[meta][i]")
    spec = InputSpec({"meta": "dict[str, object]"}, {}, (), {"load": "object"})
    program = render_program(grounded, spec)
    assert "class _Opaque:" in program.source
    assert "_Opaque()" in program.source
    assert concrete_replay(program, "f").status == "reproduced"


def test_esbmc_python_traceback_error_is_preferred_over_mypy_noise():
    from research_pipeline.scan.capability import diagnose_esbmc
    out = ("p.py:1: error: Function is missing a type annotation  [no-untyped-def]\n"
           "Traceback (most recent call last):\n  File \"x.py\", line 3\n"
           "TypeError: __init__() takes 1 positional argument but 2 were given\n")
    assert diagnose_esbmc("tool_error", out, "").message.startswith("TypeError: __init__()")


def test_library_chains_are_flattened_to_one_level():
    source = ("import email.utils\nimport http\nimport tornado.web\n\n\n"
              "class H(tornado.web.RequestHandler):\n    pass\n\n\n"
              "def f(s, status: int):\n    t = email.utils.parsedate_tz(s)\n"
              "    return 1 // len(http.RESPONSES.get(status))\n")
    grounded = _ground(source, "f", "1 // len(http.RESPONSES.get(status))")
    assert grounded.unsupported == ""
    assert grounded.stub_keys == ("email_utils.parsedate_tz", "http_RESPONSES.get")
    assert "    t = email_utils.parsedate_tz(s)\n" in grounded.module
    assert any(t.startswith("external_chains_flattened:") for t in grounded.transforms)
    spec = InputSpec({"s": "str"}, {}, (), {"email_utils.parsedate_tz": "object", "http_RESPONSES.get": "str"})
    program = render_program(grounded, spec)
    lines = program.source.splitlines()
    assert [lines[a - 1].strip() for a, _ in program.target_spans] == ["return 1 // len(http_RESPONSES.get(status))"]
    assert concrete_replay(program, "f").status == "reproduced"


def test_chain_used_as_base_class_becomes_one_opaque_class():
    source = "import tornado.web\n\n\nclass H(tornado.web.RequestHandler):\n    def go(self, n: int):\n        return 1 // n\n"
    grounded = _ground(source, "H.go", "1 // n")
    assert grounded.unsupported == ""
    assert "class H(tornado_web_RequestHandler):" in grounded.module
    assert grounded.externals.classes == {"tornado_web_RequestHandler"}


def test_class_called_as_constructor_gets_an_init():
    source = "from pandas import MultiIndex\n\n\ndef f(x, n: int):\n    if isinstance(x, MultiIndex):\n        return 0\n    m = MultiIndex(x, names=None)\n    return n // 0\n"
    grounded = _ground(source, "f", "n // 0")
    assert grounded.unsupported == "" and grounded.stub_keys == ()
    program = render_program(grounded, InputSpec({"x": "str"}, {}, ()))
    assert "class MultiIndex:\n    def __init__(self, a0, names=None) -> None:\n        pass" in program.source
    assert concrete_replay(program, "f").status == "reproduced"


def test_name_used_as_type_and_namespace_is_a_class_with_static_methods():
    source = "from pandas import MultiIndex\n\n\ndef f(x, n: int):\n    if isinstance(x, MultiIndex):\n        return 0\n    m = MultiIndex.from_tuples(x)\n    return n // m\n"
    grounded = _ground(source, "f", "n // m")
    assert grounded.unsupported == ""
    program = render_program(grounded, InputSpec({"x": "str"}, {}, (), {"MultiIndex.from_tuples": "int"}))
    assert "class MultiIndex:\n    @staticmethod\n    def from_tuples(a0) -> int:" in program.source
    assert concrete_replay(program, "f").status == "reproduced"


def test_classmethod_target_is_called_on_the_class():
    source = "class K:\n    LIMIT = 0\n\n    @classmethod\n    def make(cls, a: int):\n        return a // cls.LIMIT\n"
    grounded = _ground(source, "K.make", "a // cls.LIMIT")
    assert grounded.unsupported == ""
    program = render_program(grounded, InputSpec({}, {}, ()))
    assert "    K.make(a)\n" in program.source and "LIMIT = 0" in program.source
    assert concrete_replay(program, "make").status == "reproduced"


def test_init_target_runs_the_real_constructor():
    source = "class A:\n    def __init__(self, x: int, y: int):\n        self.r = x // y\n\n    def other(self):\n        return 1\n"
    grounded = _ground(source, "A.__init__", "x // y")
    assert grounded.unsupported == ""
    program = render_program(grounded, InputSpec({}, {}, ()))
    assert "        self.r = x // y\n" in program.source
    assert "    A(x, y)\n" in program.source
    assert concrete_replay(program, "__init__").status == "reproduced"


def test_failed_original_assert_maps_to_assertion_error():
    kinds = ["assertion ISINSTANCE(param, 0)", "unwinding assertion loop 131"]
    reading = classify_esbmc(ESBMCDirectResult(
        source_file="p.py", status="violation_found", command=["esbmc"], returncode=1, summary="",
        details={"violated_properties": kinds, "violated_files": ["", "x.c"]}))
    assert final_verdict(reading, ReplayVerdict("reproduced", "AssertionError", 14)) == CONFIRMED
    unwinding = classify_esbmc(ESBMCDirectResult(
        source_file="p.py", status="violation_found", command=["esbmc"], returncode=1, summary="",
        details={"violated_properties": ["unwinding assertion loop 3", "dereference failure: invalid pointer"],
                 "violated_files": ["", ""]}))
    assert "AssertionError" not in unwinding.exceptions


def test_replay_ignores_annotations_the_host_does_not_know():
    source = ("def isqrt(n: uint64) -> uint64:\n    return 10 // n\n\n\n"
              "def _esbmc_main() -> None:\n    n: int = nondet_int()\n    isqrt(n)\n\n\n_esbmc_main()\n")
    from research_pipeline.verify.render import Program
    program = Program(source, 5, ((2, 2),), (), (1, 2))
    verdict = concrete_replay(program, "isqrt")
    assert (verdict.status, verdict.exception_type) == ("reproduced", "ZeroDivisionError")
