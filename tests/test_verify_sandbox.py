import pytest

from research_pipeline.verify.sandbox import host_replay_problem


def test_pure_computation_may_run_on_the_host():
    assert host_replay_problem("import math\nfrom typing import Optional\n\ndef f(x):\n    return math.floor(x)\n") == ""


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("import os\n", "imports os"),
        ("from subprocess import run\n", "imports subprocess"),
        ("from . import sibling\n", "relative module"),
        ("data = open('x').read()\n", "uses open"),
        ("eval('1')\n", "uses eval"),
        ("x = f.__globals__\n", "introspection attribute __globals__"),
        ("x = ().__class__.__bases__[0].__subclasses__()\n", "introspection attribute"),
        ("def g():\n    yield 1\nx = g().gi_frame\n", "introspection attribute gi_frame"),
        ("def f(:\n", "syntax error"),
        ("from typing import sys\n", "imports sys from typing"),
        ("import typing\nx = typing.sys\n", "introspection attribute sys"),
        ("import collections\nx = collections._sys\n", "introspection attribute _sys"),
        ("from operator import attrgetter\n", "imports attrgetter from operator"),
        ("x = getattr(object, '__subcl' + 'asses__')\n", "getattr without a literal attribute name"),
        ("x = getattr(object, '__dict__')\n", "getattr without a literal attribute name"),
        ("async def g():\n    yield 1\nc = g().ag_code\n", "introspection attribute ag_code"),
        ("def h():\n    pass\nc = h.co_names\n", "introspection attribute co_names"),
    ],
)
def test_host_access_is_refused(source, reason):
    assert reason in host_replay_problem(source)


def test_protocol_methods_are_ordinary_code():
    source = "class A:\n    def __len__(self):\n        return 0\n    def __eq__(self, o):\n        return True\n\nA().__len__()\n"
    assert host_replay_problem(source) == ""


def test_literal_attribute_access_stays_allowed():
    assert host_replay_problem("class A:\n    x = 1\n\nv = getattr(A(), 'x', None)\nok = hasattr(A, 'x')\n") == ""
