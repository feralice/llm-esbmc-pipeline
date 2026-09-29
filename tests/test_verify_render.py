import ast

import pytest

from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.render import RenderError, render_program
from research_pipeline.verify.spec import InputSpec

SOURCE = '''def ratio(total, count):
    return total // count


class Tracker:
    """Keeps definitions."""

    def __init__(self, mode, cfg):
        self.mode = mode
        self.previous_defs = cfg.load()

    def __len__(self):
        return len(self.previous_defs)

    def maybe(self, depth: int):
        while self.previous_defs and self.previous_defs[-1] >= depth:
            self.previous_defs.pop()
        return self.mode

    def unrelated(self):
        return self.cfg.reload()
'''

MAYBE = '''    def maybe(self, depth: int):
        while self.previous_defs and self.previous_defs[-1] >= depth:
            self.previous_defs.pop()
        return self.mode
'''


def _ground(function, expression):
    grounded = ground(BugHypothesis("x.py", function, expression), SOURCE)
    assert isinstance(grounded, Grounded)
    return grounded


def test_free_function_driver_declares_inputs_and_calls_target():
    program = render_program(_ground("ratio", "total // count"),
                             InputSpec({"total": "int", "count": "int"}, {}, ()))
    ast.parse(program.source)
    assert "    total: int = nondet_int()\n    count: int = nondet_int()\n    ratio(total, count)\n" in program.source
    assert program.source.rstrip().endswith("main()")
    lines = program.source.splitlines()
    assert lines[program.driver_start - 1] == "def _esbmc_main() -> None:"
    assert [lines[a - 1].strip() for a, _ in program.target_spans] == ["return total // count"]


def test_optional_uses_if_statement_not_ternary():
    program = render_program(_ground("ratio", "total // count"),
                             InputSpec({"total": "Optional[int]", "count": "list[str]"}, {}, ()))
    assert "    total: Optional[int] = None\n    if nondet_bool():\n        total = nondet_int()\n" in program.source
    assert "count: list[str] = nondet_list(3, elem_type=nondet_str())" in program.source
    assert " else " not in program.source
    assert program.source.startswith("from typing import Optional\n")
    assert "typing_import_added" in program.transforms


def test_method_keeps_target_verbatim_and_replaces_constructor():
    spec = InputSpec({}, {"mode": "str", "previous_defs": "list[int]"}, ("depth >= 0", "len(self.previous_defs) > 0"))
    program = render_program(_ground("Tracker.maybe", "self.previous_defs.pop()"), spec)
    ast.parse(program.source)
    assert MAYBE in program.source
    assert "cfg.load()" not in program.source
    assert "def __len__(self):" in program.source
    assert "def unrelated" not in program.source
    assert "        _attr_previous_defs: list[int] = nondet_list(3, elem_type=nondet_int())\n" \
           "        self.previous_defs: list[int] = _attr_previous_defs\n" in program.source
    assert "    _receiver = Tracker()\n" in program.source
    assert "    __ESBMC_assume(depth >= 0)\n    __ESBMC_assume(len(_receiver.previous_defs) > 0)\n" in program.source
    assert "    _receiver.maybe(depth)\n" in program.source
    assert set(program.transforms) == {"receiver_init_replaced", "unreachable_methods_removed:unrelated"}
    lines = program.source.splitlines()
    assert [lines[a - 1].strip() for a, _ in program.target_spans] == ["self.previous_defs.pop()"]


def test_class_without_constructor_gets_one_after_docstring():
    source = 'class K:\n    """Doc."""\n\n    def get(self, i: int):\n        return self.xs[i]\n'
    grounded = ground(BugHypothesis("k.py", "K.get", "self.xs[i]"), source)
    program = render_program(grounded, InputSpec({}, {"xs": "list[int]"}, ()))
    assert program.source.startswith('class K:\n    """Doc."""\n    def __init__(self) -> None:\n')
    assert "receiver_init_added" in program.transforms


def test_unsupported_entry_point_raises():
    source = "class K:\n    def make():\n        return 1 // 0\n"
    grounded = ground(BugHypothesis("k.py", "K.make", "1 // 0"), source)
    with pytest.raises(RenderError):
        render_program(grounded, InputSpec({}, {}, ()))


def test_invalid_spec_raises():
    with pytest.raises(RenderError):
        render_program(_ground("ratio", "total // count"), InputSpec({"total": "dict"}, {}, ()))


def test_methods_named_in_the_class_body_are_kept():
    source = ('class Req:\n    def __init__(self, raw):\n        self.raw = raw\n\n'
              '    def _get_body(self):\n        return self._body\n\n'
              '    body = property(_get_body)\n\n'
              '    def first(self):\n        return self.raw[0]\n')
    grounded = ground(BugHypothesis("r.py", "Req.first", "self.raw[0]"), source)
    program = render_program(grounded, InputSpec({}, {"raw": "list[int]", "_body": "int"}, ()))
    assert "def _get_body(self):" in program.source
    assert not any(t.startswith("unreachable_methods_removed") for t in program.transforms)


def test_keyword_only_argument_is_passed_by_name():
    grounded = ground(BugHypothesis("f.py", "f", "a // key"), "def f(a, *args, key, **kwargs):\n    return a // key\n")
    program = render_program(grounded, InputSpec({"a": "int", "key": "int"}, {}, ()))
    assert "    f(a, key=key)\n" in program.source


def test_grounding_transforms_are_carried_into_the_program():
    source = "from app import for_app\n\n\n@for_app('php')\ndef match(command: str):\n    return command.split()[1]\n"
    program = render_program(ground(BugHypothesis("m.py", "match", "command.split()[1]"), source), InputSpec({}, {}, ()))
    assert "decorators_removed:for_app('php')" in program.transforms
    lines = program.source.splitlines()
    assert [lines[a - 1].strip() for a, _ in program.target_spans] == ["return command.split()[1]"]
