from research_pipeline.verify.grounding import ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.oracle import refusals
from research_pipeline.verify.render import render_program
from research_pipeline.verify.slicing import stub_imports
from research_pipeline.verify.spec import InputSpec, spec_problems

PROGRAM = """import re
import threading as th
import os.path as osp
from re import sub, compile


def f(s, xs):
    t = re.sub("a", "", s)
    u = sub("b", "", s)
    m = re.match("a", s)
    lock = th.RLock()
    return osp.join(t, u)
"""


def test_refusals_map_each_diagnostic_to_the_imported_member():
    diagnostics = "\n".join([
        "WARNING: Undefined function 'sub' - replacing with assert(false)",
        "WARNING: Undefined function 'join' - replacing with assert(false)",
        "ERROR: program.py:11: th.RLock is not yet supported by ESBMC. Only threading.Lock is currently modelled",
        "WARNING: no operational model for module 'requests'; its names will be unresolved",
    ])
    assert refusals(diagnostics, PROGRAM) == {"re.sub", "os.path.join", "threading.RLock", "requests"}


def test_an_undefined_name_the_program_defines_refuses_no_library_member():
    program = PROGRAM + "\n\nclass C:\n    def sub(self):\n        return self.missing()\n"
    assert refusals("WARNING: Undefined function 'sub' - replacing with assert(false)", program) == set()
    assert refusals("ERROR: Type inference failed at line 3", PROGRAM) == set()


def test_refused_member_gets_a_fresh_stub_and_the_import_stays():
    program = PROGRAM + "\n\ndef _esbmc_re_sub(x):\n    return x\n"
    module, plan, transforms = stub_imports(program, frozenset({"re.sub"}))
    assert 't = _esbmc_re_sub_1("a", "", s)' in module and 'u = _esbmc_re_sub_1("b", "", s)' in module
    assert 'm = re.match("a", s)' in module
    assert "import re\n" in module and "from re import sub, compile" in module
    assert "_esbmc_re_sub_1" in plan.calls
    assert "esbmc_refused_members_stubbed:_esbmc_re_sub_1" in transforms


def test_refused_member_with_a_fixed_model_renders_the_model():
    source = "import threading\n\n\ndef f(n: int):\n    lock = threading.RLock()\n    with lock:\n        return 10 // n\n"
    module, plan, transforms = stub_imports(source, frozenset({"threading.RLock"}))
    assert plan.models == {"_esbmc_threading_RLock": "threading.RLock"}
    assert "_esbmc_threading_RLock" not in plan.stub_keys
    assert "member_models:threading.RLock" in transforms
    grounded = ground(BugHypothesis("x.py", "f", "10 // n"), source, frozenset({"threading.RLock"}))
    program = render_program(grounded, InputSpec({}, {}, ()))
    namespace = {}
    exec(program.replay_source.split("def _esbmc_main")[0], namespace)
    assert namespace["f"](5) == 2


def test_unpacked_stub_result_must_be_a_tuple_of_that_many_items():
    source = "import requests\n\n\ndef f(u):\n    code, body = requests.fetch(u)\n    return 10 // code\n"
    grounded = ground(BugHypothesis("x.py", "f", "10 // code"), source)
    assert grounded.externals.unpacked == {"requests.fetch": 2}
    for wrong in ("int", "tuple[int]", "Optional[tuple[int, str]]"):
        problems = spec_problems(InputSpec({"u": "str"}, {}, (), {"requests.fetch": wrong}), grounded)
        assert problems == ["stub 'requests.fetch': the code unpacks its result into 2 names, "
                            f"so it needs tuple[...] with 2 items, not {wrong!r}"]
    assert spec_problems(InputSpec({"u": "str"}, {}, (), {"requests.fetch": "tuple[int, str]"}), grounded) == []


def test_unpacked_input_or_field_must_be_a_tuple_of_that_many_items():
    source = "def f(size, arr):\n    w, h = size\n    n, c = arr.shape\n    return 10 // (w - n)\n"
    grounded = ground(BugHypothesis("x.py", "f", "10 // (w - n)"), source)
    assert grounded.unpacked_inputs == {"size": 2, "arr.shape": 2}
    wrong = InputSpec({"size": "list[int]", "arr": "object"}, {}, (), {"arr.shape": "int"})
    assert spec_problems(wrong, grounded) == [
        "input 'size': the code unpacks it into 2 names, so it needs tuple[...] with 2 items, not 'list[int]'",
        "input 'arr.shape': the code unpacks it into 2 names, so it needs tuple[...] with 2 items, not 'int'"]
    right = InputSpec({"size": "tuple[int, int]", "arr": "object"}, {}, (), {"arr.shape": "tuple[int, int]"})
    assert spec_problems(right, grounded) == []


def test_rebound_or_ambiguous_unpacking_adds_no_constraint():
    source = ("def f(x, y, z):\n    x = x.split(',')\n    a, b = x\n    c, d = y\n    e, f2, g = y\n"
              "    def inner(z):\n        p, q = z\n    return a\n")
    grounded = ground(BugHypothesis("x.py", "f", "a"), source)
    assert grounded.unpacked_inputs == {}
