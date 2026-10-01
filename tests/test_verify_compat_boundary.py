import ast
from dataclasses import replace

import pytest

from research_pipeline.verify.compat import rewrite_compat
from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.render import render_program
from research_pipeline.verify.replay import concrete_replay
from research_pipeline.verify.spec import InputSpec


def _render(source, expression, params):
    grounded = ground(BugHypothesis('x.py', 'f', expression), source)
    assert isinstance(grounded, Grounded)
    return grounded, render_program(grounded, InputSpec(params, {}, ()))


def test_grounding_keeps_percent_and_render_preserves_replay_source():
    source = 'def f(x):\n    text = "%s" % x\n    return 1 // len(text)\n'
    grounded, program = _render(source, '1 // len(text)', {'x': 'str'})
    assert source in grounded.module
    assert not any(t.startswith('compat_') for t in grounded.transforms)
    assert source in program.replay_source
    assert 'str(x)' in program.source and '"%s" % x' not in program.source
    assert 'compat_percent_format:1' in program.transforms


@pytest.mark.parametrize('original,rewritten,status', [
    ('return 1', 'return 1 // 0', 'not_reproduced'),
    ('return 1 // 0', 'return 1', 'reproduced'),
])
def test_replay_does_not_use_rewritten_behavior(original, rewritten, status):
    _, program = _render(f'def f():\n    {original}\n', original, {})
    program = replace(program, source=program.source.replace(original, rewritten))
    assert concrete_replay(program, 'f').status == status


def test_host_safety_checks_the_source_that_will_run():
    _, program = _render('def f():\n    return 1\n', '1', {})
    program = replace(program, replay_source="import os\nos.remove('do-not-run')\n")
    assert concrete_replay(program, 'f').status == 'unavailable'


@pytest.mark.parametrize('fmt,kind,values', [
    ('%s', 'str', ['', 'a', "é\n'\\"]),
    ('%r', 'int', [-2, 0, 3]),
    ('%d', 'int', [-2, 0, 3]),
    ('%d', 'bool', [False, True]),
    ('%d', 'float', [-1.9, 0.0, 1.9, float('nan'), float('inf')]),
])
def test_scalar_formats_preserve_values_and_exceptions(fmt, kind, values):
    source = f'def f(x):\n    return {fmt!r} % x\n'
    rewritten, transforms = rewrite_compat(source, parameter_types={'f': {'x': kind}})
    assert transforms == ['compat_percent_format:1']
    original_ns, rewritten_ns = {}, {}
    exec(source, original_ns)
    exec(rewritten, rewritten_ns)
    def outcome(fn, value):
        try:
            return fn(value)
        except Exception as exc:
            return type(exc)
    for value in values:
        assert outcome(original_ns['f'], value) == outcome(rewritten_ns['f'], value)


def test_multiline_unicode_literal_repr_preserves_precedence_and_line_count():
    source = '''def f():
    return ("é%r" % (
        "a'b\\\\c",
    )) * 2
'''
    rewritten, transforms = rewrite_compat(source)
    original_ns, rewritten_ns = {}, {}
    exec(source, original_ns)
    exec(rewritten, rewritten_ns)
    assert transforms == ['compat_percent_format:1']
    assert original_ns['f']() == rewritten_ns['f']()
    assert len(source.splitlines()) == len(rewritten.splitlines())


@pytest.mark.parametrize('body,types', [
    ('"%s" % x', {}),
    ('"%s" % x', {'x': 'tuple[int, int]'}),
    ('"%d" % x', {'x': 'str'}),
    ('"%r" % x', {'x': 'str'}),
    ('"%03d" % x', {'x': 'int'}),
    ('"%.2f" % x', {'x': 'float'}),
    ('"%s %s" % (x,)', {'x': 'str'}),
    ('"%(x)s" % x', {'x': 'dict[str, str]'}),
    ('"%d %s" % (x, +y)', {'x': 'float', 'y': 'str'}),
])
def test_uncertain_or_unsupported_formats_are_unchanged(body, types):
    source = f'def f(x, y=None):\n    return {body}\n'
    assert rewrite_compat(source, parameter_types={'f': types}) == (source, [])


@pytest.mark.parametrize('prefix', [
    '    x = (1, 2)\n',
    '    import math as x\n',
    '    match (1, 2):\n        case x:\n            pass\n',
    '    def x():\n        return 1\n',
])
def test_rebound_parameter_does_not_inherit_driver_type(prefix):
    source = f'def f(x):\n{prefix}    return "%s" % x\n'
    assert rewrite_compat(source, parameter_types={'f': {'x': 'str'}}) == (source, [])


def test_annotations_and_recursive_calls_are_not_type_guarantees():
    for source in [
        'def f(x: str):\n    return "%s" % x\n',
        'def f(x):\n    if x:\n        return f((1, 2))\n    return "%s" % x\n',
    ]:
        types = {} if 'x: str' in source else {'f': {'x': 'str'}}
        assert rewrite_compat(source, parameter_types=types) == (source, [])


def test_nested_scope_does_not_inherit_parameter_type():
    source = 'def f(x):\n    def inner(x):\n        return "%s" % x\n    return inner((1, 2))\n'
    assert rewrite_compat(source, parameter_types={'f': {'x': 'str'}}) == (source, [])


def test_shadowed_conversion_builtin_is_not_called_by_rewrite():
    source = 'def f(x, str):\n    return "%s" % x\n'
    assert rewrite_compat(source, parameter_types={'f': {'x': 'str'}}) == (source, [])


def test_replay_maps_original_multiline_operand():
    source = 'def f():\n    return "%s" % (\n        1 // 0,\n    )\n'
    _, program = _render(source, '1 // 0', {})
    assert program.replay_target_spans == ((3, 3),)
    assert program.target_spans == ((2, 2),)
    verdict = concrete_replay(program, 'f')
    assert (verdict.status, verdict.line) == ('reproduced', 3)
    assert ast.parse(program.source)


def test_legacy_program_with_rewrites_requires_original_for_replay():
    _, program = _render('def f():\n    return 1 // 0\n', '1 // 0', {})
    program = replace(program, replay_source=None, transforms=('compat_percent_format:1',))
    assert concrete_replay(program, 'f').status == 'unavailable'


def test_format_does_not_dispatch_to_custom_addition():
    source = 'def f(x, y):\n    return "%s %s" % (x, y)\n'
    rewritten, _ = rewrite_compat(source)

    class Hostile(str):
        def __add__(self, other):
            return "added"
        __radd__ = __add__

    class Value:
        def __str__(self):
            return Hostile("v")
    original_ns, rewritten_ns = {}, {}
    exec(source, original_ns)
    exec(rewritten, rewritten_ns)
    assert rewritten_ns['f'](Value(), Value()) == original_ns['f'](Value(), Value()) == "v v"


def test_escaped_surrogate_in_format_remains_encodable_source():
    source = 'def f():\n    return "\\ud800%s" % (1,)\n'
    rewritten, transforms = rewrite_compat(source)
    assert transforms == ['compat_percent_format:1']
    namespace = {}
    exec(rewritten, namespace)
    assert namespace['f']() == '\ud8001'


def test_non_bmp_unicode_format_preserves_the_python_string():
    source = 'def f():\n    return "😀%s" % (1,)\n'
    rewritten, transforms = rewrite_compat(source)
    assert transforms == ['compat_percent_format:1']
    namespace = {}
    exec(rewritten, namespace)
    assert namespace['f']() == '😀1'


def test_implicit_constructor_calls_do_not_inherit_driver_types():
    source = ('class C:\n    def __init__(self, x):\n        self.label = "%s" % x\n'
              'C((1, 2))\nC("text")\n')
    assert rewrite_compat(source, parameter_types={'C.__init__': {'x': 'str'}}) == (source, [])


@pytest.mark.parametrize('body', [
    'return "id=%s" % re.match("a(b)?", m).group(1)',
    'return "^(%s)$" % "|".join(xs)',
    'w = re.search("a", m).group()\n    return "v=%s" % w',
    'v = "a, ".strip()\n    v = f"{n}"\n    return "[%s]" % v',
    'return "<%s %s>" % (xs, m)',
])
def test_exact_strings_and_tuple_names_format_exactly_as_str(body):
    source = f'import re\n\n\ndef f(m, xs, n):\n    {body}\n'
    rewritten, transforms = rewrite_compat(source)
    assert transforms == ['compat_percent_format:1']

    class Rmod(str):
        def __rmod__(self, other):
            return ('rmod',)
    for m, xs, n in [('ab', ['a', 'b'], 3), ('zz', [], (1, 2)), (Rmod('ab'), Rmod('x'), Rmod('y'))]:
        original_ns, rewritten_ns = {}, {}
        exec(source, original_ns)
        exec(rewritten, rewritten_ns)
        def outcome(fn):
            try:
                return fn(m, xs, n)
            except Exception as exc:
                return type(exc)
        assert outcome(original_ns['f']) == outcome(rewritten_ns['f'])


@pytest.mark.parametrize('body', [
    'return "%s" % m.group(1)',
    'return "%s" % re.match("a", m).group(1, 2)',
    'return "%s" % re.match("a", m).group(*xs)',
    'v = str(n)\n    return "%s" % v',
    'return "%s" % abs(n)',
    'return "%s" % n.format()',
    'v = "a"\n    from os import sep as v\n    return "%s" % v',
    'v = "a"\n    v, w = n\n    return "%s" % v',
    'for v in xs:\n        return "%s" % v',
    'return "%s" % m.lookup(1)',
    'v = re.search("(?P<id>a)", m)\n    w = v.group("id") if v else None\n    return "v=%s" % w',
])
def test_values_not_proven_exact_str_are_left_alone(body):
    source = f'import re\n\n\ndef f(m, xs, n):\n    {body}\n'
    assert rewrite_compat(source) == (source, [])
