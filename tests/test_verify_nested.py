import ast

from research_pipeline.verify.agent_arm import nested_hint
from research_pipeline.verify.astutil import find_definition, outer_entry
from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.render import render_program
from research_pipeline.verify.spec import InputSpec
from research_pipeline.verify.validation import program_for_result, target_preserved

FOUR_LEVELS = '''class A:
    def f(self, n: int) -> int:
        def g(k: int) -> int:
            def h(m: int) -> int:
                def i(z: int) -> int:
                    return 10 // (z - n + k)
                return i(m)
            return h(k)
        return g(n)
'''

NONLOCAL = '''def f(n: int) -> int:
    total = 0
    def add(x: int) -> None:
        nonlocal total
        total = total + 10 // x
    add(n)
    return total
'''

INNER_CLASS = '''def f(n: int) -> int:
    k = n - 1
    class C:
        def m(self) -> int:
            return 10 // k
    return C().m()
'''

CALLBACK = '''def f(request, n: int) -> None:
    def cb(x: int) -> int:
        return 10 // x
    request.errback = cb
'''

RETURNED = '''def outer(n: int):
    def inner(x: int) -> int:
        return x // n
    return inner
'''

TWO_BRANCHES = '''def f(n: int, fast: bool) -> int:
    if fast:
        def g(k: int) -> int:
            return k
    else:
        def g(k: int) -> int:
            return 10 // k
    return g(n)
'''

ASYNC_OUTER = '''async def f(n: int) -> int:
    def g(k: int) -> int:
        return 10 // k
    return g(n)
'''


def test_find_definition_resolves_any_depth():
    assert find_definition(ast.parse(FOUR_LEVELS), "A.f.g.h.i").name == "i"
    assert find_definition(ast.parse(FOUR_LEVELS), "A.f.g.x") is None


def test_outer_entry_when_every_link_calls_the_next():
    assert outer_entry(ast.parse(FOUR_LEVELS), "A.f.g.h.i") == "A.f"
    assert outer_entry(ast.parse(NONLOCAL), "f.add") == "f"
    assert outer_entry(ast.parse(INNER_CLASS), "f.C.m") == "f"


def test_no_outer_entry_for_a_callback_or_a_returned_closure():
    assert outer_entry(ast.parse(CALLBACK), "f.cb") is None
    assert outer_entry(ast.parse(RETURNED), "outer.inner") is None


def test_outer_entry_picks_the_branch_holding_the_expression():
    assert outer_entry(ast.parse(TWO_BRANCHES), "f.g", "10 // k") == "f"


def test_no_outer_entry_through_an_async_function():
    assert outer_entry(ast.parse(ASYNC_OUTER), "f.g") is None


def _ground(name, expression, line, source) -> Grounded:
    grounded = ground(BugHypothesis("x.py", name, expression, line=line), source)
    assert isinstance(grounded, Grounded), grounded
    return grounded


def test_nonlocal_and_inner_class_ground_through_the_outer_function():
    for source, name, expression in [(NONLOCAL, "f.add", "10 // x"), (INNER_CLASS, "f.C.m", "10 // k")]:
        grounded = _ground(name, expression, 5, source)
        assert grounded.transforms[0] == f"nested_entry_via_outer:{name}"
        assert grounded.hypothesis.function == "f"


def test_four_levels_enter_through_the_method():
    grounded = _ground("A.f.g.h.i", "10 // (z - n + k)", 6, FOUR_LEVELS)
    assert grounded.transforms[0] == "nested_entry_via_outer:A.f.g.h.i"
    assert grounded.hypothesis.function == "A.f"
    assert grounded.hypothesis.line == 6


def test_callback_and_async_outer_still_hoist():
    assert _ground("f.cb", "10 // x", 3, CALLBACK).transforms[0].startswith("nested_entry_hoisted:")
    assert _ground("f.g", "10 // k", 3, ASYNC_OUTER).transforms[0].startswith("nested_entry_hoisted:")


def test_target_preserved_sees_an_untouched_nested_function():
    assert target_preserved(FOUR_LEVELS, FOUR_LEVELS, "A.f.g.h.i")
    assert not target_preserved(FOUR_LEVELS, FOUR_LEVELS.replace("10 //", "11 //"), "A.f.g.h.i")


def test_target_preserved_matches_the_hoisted_copy():
    grounded = _ground("f.cb", "10 // x", 3, CALLBACK)
    program = render_program(grounded, InputSpec({p.name: "int" for p in grounded.params}, {}, ()))
    assert target_preserved(CALLBACK, program.source, grounded.hypothesis.function)
    assert not target_preserved(CALLBACK, program.source.replace("10 // x", "10 // (x + 1)"),
                                grounded.hypothesis.function)


def test_program_for_result_finds_a_nested_target(tmp_path):
    path = tmp_path / "p.py"
    path.write_text(FOUR_LEVELS)
    program = program_for_result(path, {"function": "A.f.g.h.i", "suspect_expression": "10 // (z - n + k)"})
    assert program is not None and program.target_spans == ((6, 6),)


def test_agent_prompt_says_where_a_nested_target_lives():
    assert "defined inside `f`" in nested_hint(CALLBACK, "f.cb")
    assert nested_hint(CALLBACK, "f") == ""
    assert nested_hint("def broken(:\n", "f.cb") == ""
