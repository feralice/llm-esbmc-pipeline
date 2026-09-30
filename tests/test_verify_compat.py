import ast

from research_pipeline.verify.compat import rewrite_compat
from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis


def test_percent_s_with_tuple_literal_becomes_str_concatenation():
    source = 'def label(code, name):\n    return "id=%s:%s!" % (code, name)\n'
    rewritten, transforms = rewrite_compat(source)
    assert '    return "id=" + str(code) + ":" + str(name) + "!"\n' in rewritten
    assert transforms == ["compat_percent_format:1"]


def test_equivalence_under_cpython_for_sample_values():
    source = 'def label(a, b):\n    return "%s-%s" % (a, b)\n'
    rewritten, _ = rewrite_compat(source)
    for a, b in [(1, "x"), (None, 2.5), ("", []), ((1, 2), {"k": 1})]:
        original_ns, new_ns = {}, {}
        exec(source, original_ns)
        exec(rewritten, new_ns)
        assert original_ns["label"](a, b) == new_ns["label"](a, b)


def test_other_conversions_and_non_tuple_operands_are_left_alone():
    for body in ['"%d items" % (n,)', '"%s" % n', '"%s %s" % pair', '"%(k)s" % mapping', '"%s %s" % (a,)']:
        source = f"def f(n, pair, mapping, a):\n    return {body}\n"
        assert rewrite_compat(source) == (source, [])


def test_literal_percent_is_kept():
    source = 'def f(a):\n    return "%s is 100%%" % (a,)\n'
    rewritten, _ = rewrite_compat(source)
    assert 'return str(a) + " is 100%"' in rewritten


def test_grounding_applies_the_rewrite_and_keeps_line_numbers():
    source = 'def label(code, name):\n    msg = "%s %s" % (code, name)\n    return 1 // len(msg)\n'
    grounded = ground(BugHypothesis("x.py", "label", "1 // len(msg)"), source)
    assert isinstance(grounded, Grounded)
    assert 'msg = str(code) + " " + str(name)' in grounded.module
    assert "compat_percent_format:1" in grounded.transforms
    assert ast.parse(grounded.module)


ALIAS_SOURCE = (
    "class R:\n"
    "    def __str__(self) -> str:\n"
    "        return 'r'\n"
    "\n"
    "    __repr__ = __str__\n"
    "\n"
    "    def scale(self, k, *, by=2):\n"
    "        return k * by\n"
    "\n"
    "    times = scale\n"
    "    LIMIT = 3\n"
    "    other = LIMIT\n"
)


def test_method_alias_becomes_one_line_delegating_def():
    rewritten, transforms = rewrite_compat(ALIAS_SOURCE)
    lines = rewritten.splitlines()
    assert lines[4] == "    def __repr__(self) -> str: return self.__str__()"
    assert lines[9] == "    def times(self, k, *, by=2): return self.scale(k, by=by)"
    assert "    other = LIMIT" in lines
    assert len(lines) == len(ALIAS_SOURCE.splitlines())
    assert "compat_method_alias:2" in transforms


def test_method_alias_rewrite_is_equivalent_under_cpython():
    original, rewritten = {}, {}
    exec(ALIAS_SOURCE, original)
    exec(rewrite_compat(ALIAS_SOURCE)[0], rewritten)
    for ns in (original, rewritten):
        r = ns["R"]()
        assert (repr(r), r.times(3), r.times(3, by=5)) == ("r", 6, 15)


def test_alias_of_static_or_variadic_method_is_left_alone():
    source = (
        "class R:\n"
        "    @staticmethod\n"
        "    def make():\n"
        "        return 1\n"
        "    build = make\n"
        "    def many(self, *xs):\n"
        "        return xs\n"
        "    lots = many\n"
    )
    rewritten, transforms = rewrite_compat(source)
    assert rewritten == source and transforms == []
