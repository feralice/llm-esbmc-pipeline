import ast

from research_pipeline.verify.astutil import find_definition, outer_entry

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
