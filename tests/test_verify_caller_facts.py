import ast

from research_pipeline.scan.callgraph import build_callgraph
from research_pipeline.verify.caller_facts import (
    MAX_CALLER_CHARS,
    CallerFacts,
    collect_facts,
    function_key,
    literal_type,
    render_section,
)
from research_pipeline.verify.grounding import ground
from research_pipeline.verify.hypothesis import BugHypothesis

SOURCE = (
    "import re\n"                                                   # 1
    "from functools import partial\n"                               # 2
    "\n"                                                            # 3
    "def convert(string, match, ymd=None, d_m_y=None):\n"           # 4
    "    groups = match.groups()\n"                                 # 5
    "    return groups[ymd] + string\n"                             # 6
    "\n"                                                            # 7
    "def register(n):\n"                                            # 8
    "    return partial(convert, ymd=n + 1)\n"                      # 9
    "\n"                                                            # 10
    "def use(s):\n"                                                 # 11
    "    m = re.match('x', s)\n"                                    # 12
    "    return convert(s, m, 2, d_m_y=(1, 2, 3))\n"                # 13
)


def _facts(source=SOURCE, function="convert", expression="groups[ymd] + string", file="pkg/x.py", graph=None):
    h = BugHypothesis(file, function, expression)
    return collect_facts(h, ground(h, source), source, graph=graph), ground(h, source)


def test_literal_types_cover_constants_negatives_and_containers():
    def kind(text):
        return literal_type(ast.parse(text, mode="eval").body)

    assert [kind(t) for t in ("None", "True", "3", "-2.5", "'a'", "f'{x}'", "[1]", "(1,)", "{}", "{1}")] == [
        "None", "bool", "int", "float", "str", "str", "list", "tuple", "dict", "set"]
    assert kind("x") is None and kind("-x") is None and kind("n + 1") is None


def test_facts_from_the_verification_file_alone():
    facts, _ = _facts()
    assert facts.site_count == 1
    assert "return convert(s, m, 2, d_m_y=(1, 2, 3))" in facts.sites
    assert facts.passed == {"ymd": {"int": 1}, "d_m_y": {"tuple": 1}}
    assert facts.defaults == {"ymd": "None", "d_m_y": "None"}
    assert facts.usage == {}
    assert any("partial(convert, ymd=n + 1)" in line for line in facts.references)


def test_usage_marks_subscript_iteration_and_len():
    source = "def f(a, b, c, d):\n    for x in b:\n        pass\n    return a[0] + len(c) + d\n"
    facts, _ = _facts(source, "f", "a[0] + len(c) + d")
    assert facts.usage["a"].subscripted and facts.usage["b"].iterated and facts.usage["c"].sized
    assert "d" not in facts.usage


def test_rebound_shadowed_and_type_tested_inputs_are_unchecked():
    source = ("def f(a, b, c, d):\n    a = str(a)\n    g = lambda b: b\n"
              "    if isinstance(c, int):\n        return 0\n    return a[0] + g(b)[0] + c[0] + d[0]\n")
    facts, _ = _facts(source, "f", "a[0] + g(b)[0] + c[0] + d[0]")
    assert facts.unchecked == frozenset({"a", "b", "c"})
    assert set(facts.usage) == {"d"}


def test_method_called_unbound_through_the_class_binds_keywords_only():
    source = ("class C:\n    def m(self, x, y=0):\n        return x // y\n\n"
              "    def run(self):\n        return self.m(7, y='s')\n\n"
              "def outside(c):\n    return C.m(c, 5, y=0)\n")
    facts, _ = _facts(source, "C.m", "x // y")
    assert facts.passed == {"x": {"int": 1}, "y": {"int": 1, "str": 1}}


def test_a_function_defined_twice_gets_no_callers():
    source = "def f(a):\n    return a[0]\n\ndef f(a):\n    return a[0]\n\nf(1)\n"
    h = BugHypothesis("x.py", "f", "a[0]")
    facts = collect_facts(h, ground(h, "def f(a):\n    return a[0]\n"), source)
    assert facts.sites == "" and facts.site_count == 0 and facts.passed == {}


def test_scan_graph_finds_callers_in_other_files(tmp_path):
    (tmp_path / "calc.py").write_text("def first(xs):\n    return xs[0]\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("from calc import first\n\ndef head():\n    return first([1, 2])\n",
                                     encoding="utf-8")
    graph = build_callgraph(tmp_path)
    source = (tmp_path / "calc.py").read_text(encoding="utf-8")
    assert function_key(graph, str(tmp_path / "calc.py"), "first") == "calc:first"
    facts, _ = _facts(source, "first", "xs[0]", file=str(tmp_path / "calc.py"), graph=graph)
    assert facts.passed == {"xs": {"list": 1}} and "app.py" in facts.sites


def test_a_source_that_does_not_parse_gives_empty_facts():
    h = BugHypothesis("x.py", "f", "a[0]")
    grounded = ground(h, "def f(a):\n    return a[0]\n")
    assert collect_facts(h, grounded, "def f(:\n") == CallerFacts()


def test_section_is_bounded_and_says_when_there_are_no_callers():
    facts, grounded = _facts()
    text = render_section(facts, grounded)
    assert "Call sites" in text and "- ymd: default is None; callers pass int (1x)" in text
    assert "- d_m_y: default is None; callers pass tuple (1x)" in text
    many = "def f(a):\n    return a[0]\n" + "".join(
        f"\ndef c{i}():\n    return f([{'1, ' * 60}1])\n" for i in range(30))
    big, _ = _facts(many, "f", "a[0]")
    assert len(big.sites) <= MAX_CALLER_CHARS + 60 and "omitted" in big.sites
    lonely, grounded = _facts("def f(a):\n    return a[0]\n", "f", "a[0]")
    assert "# none found in the verification source" in render_section(lonely, grounded)


GUARDED = (
    "def head(s, n):\n"
    "    return s[0] * n\n"
    "\n"
    "def a(s, n):\n"
    "    if s is not None and len(s) > 0:\n"
    "        return head(s, n)\n"
    "\n"
    "def b(s, n):\n"
    "    if s is None or not s:\n"
    "        return ''\n"
    "    if n > 2:\n"
    "        return head(s, n)\n"
)
ONE_CALLER = GUARDED.split("def b")[0]


def _guards(source):
    return _facts(source, function="head", expression="s[0]")[0].guards


def test_only_the_guards_every_caller_has_are_kept():
    # a: s not None and len(s) > 0; b: s not None, s truthy and n > 2. Only "s not None" is in both.
    assert _guards(GUARDED) == (("s", "{} is not None"),)
    assert _guards(ONE_CALLER) == (("s", "len({}) > 0"), ("s", "{} is not None"))


def test_an_unguarded_caller_a_rebinding_or_a_use_as_value_leaves_no_guard():
    assert _guards(GUARDED + "\ndef c(s):\n    return head(s, 1)\n") == ()
    rebound = ONE_CALLER.replace("        return head(s, n)\n", "        s = None\n        return head(s, n)\n")
    assert _guards(rebound) == ()
    assert _guards(GUARDED + "\ndef d():\n    return list(map(head, [1]))\n") == ()


def test_an_early_exit_guards_the_rest_of_the_block():
    source = ("def f(x):\n    return x + 1\n\n"
              "def g(x):\n    if not isinstance(x, int):\n        raise TypeError\n    return f(x)\n")
    assert _facts(source, "f", "x + 1")[0].guards == (("x", "isinstance({}, int)"),)
    source = source.replace("if not isinstance(x, int):", "if x is None:")
    assert _facts(source, "f", "x + 1")[0].guards == (("x", "{} is not None"),)


def test_guard_assumptions_follow_the_spec_types():
    from research_pipeline.verify.caller_facts import guard_assumptions
    from research_pipeline.verify.spec import InputSpec

    facts, grounded = _facts(ONE_CALLER, "head", "s[0]")
    spec = InputSpec({"s": "Optional[str]", "n": "int"}, {}, ())
    assert guard_assumptions(facts, spec, grounded) == (("s is not None", "len(s) > 0"), [])
    assert guard_assumptions(facts, InputSpec({"s": "str", "n": "int"}, {}, ()), grounded) == (("len(s) > 0",), [])
    assumed, problems = guard_assumptions(facts, InputSpec({"s": "int", "n": "int"}, {}, ()), grounded)
    assert "len(s) > 0" in problems[0]
