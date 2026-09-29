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
