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


def test_property_and_its_getter_leave_the_class_when_the_shell_supplies_state():
    source = ('class Req:\n    def __init__(self, raw):\n        self.raw = raw\n\n'
              '    def _get_body(self):\n        return self._body\n\n'
              '    body = property(_get_body)\n\n'
              '    def first(self):\n        return self.raw[0] + self.body\n')
    grounded = ground(BugHypothesis("r.py", "Req.first", "self.raw[0]"), source)
    assert grounded.receiver_attrs == ("body", "raw")
    program = render_program(grounded, InputSpec({}, {"raw": "list[int]", "body": "int"}, ()))
    assert "property(" not in program.source and "_get_body" not in program.source
    assert "properties_as_attributes:body" in program.transforms


def test_methods_named_in_the_class_body_are_kept():
    source = ('class Req:\n    def __init__(self, raw):\n        self.raw = raw\n\n'
              '    def _check(self):\n        return True\n\n'
              '    HOOKS = [_check]\n\n'
              '    def first(self):\n        return self.raw[0]\n')
    grounded = ground(BugHypothesis("r.py", "Req.first", "self.raw[0]"), source)
    program = render_program(grounded, InputSpec({}, {"raw": "list[int]"}, ()))
    assert "def _check(self):" in program.source
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


def test_set_and_frozenset_inputs_are_built_by_adding_members():
    program = render_program(_ground("ratio", "total // count"),
                             InputSpec({"total": "set[int]", "count": "frozenset[str]"}, {}, ()))
    ast.parse(program.source)
    assert "    total: set[int] = set()\n    if nondet_bool():\n        _v1: int = nondet_int()\n        total.add(_v1)\n" in program.source
    assert "    count: frozenset[str] = frozenset(_v3)\n" in program.source


def test_unmodeled_builtin_exceptions_get_classes_with_their_cpython_bases():
    source = """def check(x: int):
    try:
        return 10 // x
    except (UnicodeDecodeError, IOError, WindowsError, LookupError):
        raise DeprecationWarning("x")
"""
    grounded = ground(BugHypothesis("x.py", "check", "10 // x"), source)
    program = render_program(grounded, InputSpec({}, {}, ()))
    ast.parse(program.source)
    for line in ("class UnicodeError(ValueError):", "class UnicodeDecodeError(UnicodeError):", "IOError = OSError",
                 "class WindowsError(Exception):", "class Warning(Exception):", "class DeprecationWarning(Warning):"):
        assert line in program.source.splitlines()
    # A stub for an ancestor of IndexError/KeyError would stop catching them.
    assert "class LookupError" not in program.source
    assert any(t.startswith("builtin_exceptions_stubbed:") for t in program.transforms)


def test_replay_keeps_cpython_exceptions_instead_of_the_stubs():
    source = """def check(raw: bytes) -> int:
    try:
        raw.decode("ascii")
    except UnicodeDecodeError:
        return 1
    except ValueError:
        return 0
    return 2
"""
    program = render_program(ground(BugHypothesis("x.py", "check", 'raw.decode("ascii")'), source), InputSpec({}, {}, ()))
    assert "class UnicodeDecodeError(UnicodeError):" in program.source.splitlines()
    assert "UnicodeError(" not in program.replay_source
    assert len(program.replay_source.splitlines()) == len(program.source.splitlines())
    namespace = {}
    exec(program.replay_source.split("def _esbmc_main")[0], namespace)
    assert namespace["check"](b"\xff") == 1


def test_stub_accepts_every_call_shape_the_code_uses():
    source = "from shapes import Path\n\n\ndef f(n: int):\n    p = Path(1, 2)\n    q = Path(3)\n    return n // 1\n"
    program = render_program(ground(BugHypothesis("x.py", "f", "n // 1"), source),
                             InputSpec({}, {}, (), {"Path": "int"}))
    assert "def Path(a0=None, a1=None) -> int:" in program.source
    namespace = {"nondet_int": lambda: 0}
    exec(program.replay_source.split("def _esbmc_main")[0], namespace)
    assert namespace["f"](4) == 4


def test_custom_new_leaves_with_the_constructor_the_shell_replaces():
    source = """class Client:
    def __new__(cls, **kwargs):
        return super(Client, cls).__new__(cls)

    def __init__(self, n):
        self.n = n

    def ratio(self):
        return 10 // self.n
"""
    program = render_program(ground(BugHypothesis("x.py", "Client.ratio", "10 // self.n"), source),
                             InputSpec({}, {"n": "int"}, ()))
    assert "__new__" not in program.source
    assert "receiver_new_removed" in program.transforms


def test_new_stays_when_it_is_the_target():
    source = """class Pool:
    def __new__(cls, size):
        return 10 // size
"""
    grounded = ground(BugHypothesis("x.py", "Pool.__new__", "10 // size"), source)
    program = render_program(grounded, InputSpec({"size": "int"}, {}, ()))
    assert "def __new__(cls, size):" in program.source
