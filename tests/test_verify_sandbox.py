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
        ("x = f.__globals__\n", "dunder attribute __globals__"),
        ("def f(:\n", "syntax error"),
    ],
)
def test_host_access_is_refused(source, reason):
    assert reason in host_replay_problem(source)
