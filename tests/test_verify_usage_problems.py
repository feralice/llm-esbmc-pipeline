from research_pipeline.verify.caller_facts import collect_facts, usage_problems
from research_pipeline.verify.grounding import ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.spec import InputSpec

SOURCE = ("def convert(match, ymd, rows, names: list):\n"
          "    groups = match.groups()\n"
          "    for row in rows:\n"
          "        pass\n"
          "    return groups[ymd] + names[0]\n")
GROUPS = ("input 'match': typed 'int', but the code uses .groups() on it, which int does not "
          "have; type it object and give each member under stubs")


def _check(params, source=SOURCE, function="convert", expression="groups[ymd] + names[0]", stubs=None):
    h = BugHypothesis("x.py", function, expression)
    grounded = ground(h, source)
    return usage_problems(InputSpec(params, {}, (), stubs or {}), grounded, collect_facts(h, grounded, source))


def test_int_with_a_called_member_is_rejected_with_the_member_named():
    assert _check({"match": "int", "ymd": "int", "rows": "list[int]"}) == [GROUPS]


def test_object_and_types_that_have_the_member_pass():
    assert _check({"match": "object", "ymd": "int", "rows": "list[int]"}, stubs={"match.groups": "list[str]"}) == []
    source = "def f(s):\n    return s.strip()[0]\n"
    assert _check({"s": "Optional[str]"}, source, "f", "s.strip()[0]") == []


def test_scalar_subscripted_or_iterated_is_rejected():
    source = "def f(a, b):\n    for x in b:\n        pass\n    return a[0]\n"
    problems = _check({"a": "int", "b": "Optional[float]"}, source, "f", "a[0]")
    assert problems == ["input 'a': typed 'int', but the code subscripts it (a[...])",
                        "input 'b': typed 'Optional[float]', but the code iterates it or passes it to len()"]
    assert _check({"a": "set[int]", "b": "str"}, source, "f", "a[0]") == [
        "input 'a': typed 'set[int]', but the code subscripts it (a[...])"]


def test_declared_annotation_is_never_questioned():
    source = "def f(a: int):\n    return a[0]\n"
    assert _check({}, source, "f", "a[0]") == []


def test_rebound_or_type_tested_input_is_never_questioned():
    source = ("def f(a, b):\n    a = str(a)\n    if isinstance(b, int):\n        return 0\n"
              "    return a.strip()[0] + b[0]\n")
    assert _check({"a": "int", "b": "int"}, source, "f", "a.strip()[0] + b[0]") == []


def test_receiver_attribute_and_member_stub_are_checked():
    source = "class C:\n    def m(self):\n        return self.re.match('x').group(1) + self.cron.RANGES.index(1)\n"
    h = BugHypothesis("x.py", "C.m", "self.cron.RANGES.index(1)")
    grounded = ground(h, source)
    spec = InputSpec({}, {"re": "str", "cron": "object"}, (), {"self.cron.RANGES": "int"})
    problems = usage_problems(spec, grounded, collect_facts(h, grounded, source))
    assert problems == [
        ("input 'self.cron.RANGES': typed 'int', but the code uses .index() on it, which int does not have; "
         "type it object and give each member under stubs"),
        ("input 'self.re': typed 'str', but the code uses .match() on it, which str does not have; "
         "type it object and give each member under stubs"),
    ]
