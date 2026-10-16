from dataclasses import replace

import pytest

from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.render import RenderError, render_program
from research_pipeline.verify.spec import InputSpec

MAGNITUDE = "def magnitude(x):\n    return x if x > 0 else x\n"
ACCOUNT = '''class Account:
    def __init__(self):
        self.balance = 0

    def deposit(self, amount):
        self.balance = self.balance - amount
'''
SCALED = "def scaled(x):\n    y = x * 2\n    return y + 1\n"
# split_conditional_assignments turns line 2 into two lines in the ESBMC copy only.
PICK = "def pick(c, x):\n    f = x if c else (lambda v: -v)\n    return x + 1\n"


def _ground(source, function, expression, oracle=VALUE_ORACLE):
    grounded = ground(BugHypothesis("m.py", function, expression, oracle=oracle), source)
    assert isinstance(grounded, Grounded)
    return grounded


def test_value_driver_asserts_the_postcondition_on_the_returned_value():
    spec = InputSpec({"x": "int"}, {}, (), returns="int", postcondition="result >= 0")
    program = render_program(_ground(MAGNITUDE, "magnitude", "x if x > 0 else x"), spec)
    assert "    _esbmc_result: int = magnitude(x)\n    assert _esbmc_result >= 0\n" in program.source
    assert program.source.splitlines()[program.property_line - 1] == "    assert _esbmc_result >= 0"
    assert program.replay_source.splitlines()[program.replay_property_line - 1] == "    assert _esbmc_result >= 0"


def test_the_property_line_follows_each_copy_when_only_the_esbmc_copy_grows():
    spec = InputSpec({"c": "bool", "x": "int"}, {}, (), returns="int", postcondition="result > x")
    program = render_program(_ground(PICK, "pick", "x + 1"), spec)
    assert any(t.startswith("conditional_assignments_split") for t in program.transforms)
    assert program.property_line == program.replay_property_line + 1
    assert program.source.splitlines()[program.property_line - 1] == "    assert _esbmc_result > x"
    assert program.replay_source.splitlines()[program.replay_property_line - 1] == "    assert _esbmc_result > x"


def test_a_method_postcondition_reads_the_receiver_after_the_call():
    spec = InputSpec({"amount": "int"}, {"balance": "int"}, (), returns="None",
                     postcondition="self.balance >= 0 or amount < 0")
    program = render_program(_ground(ACCOUNT, "Account.deposit", "self.balance - amount"), spec)
    assert "    _receiver.deposit(amount)\n    assert _receiver.balance >= 0 or amount < 0\n" in program.source
    assert "_esbmc_result" not in program.source


def test_value_hypotheses_keep_the_code_after_the_suspect():
    exception = render_program(_ground(SCALED, "scaled", "x * 2", oracle=""), InputSpec({"x": "int"}, {}, ()))
    assert any(t.startswith("cut_after_suspect") for t in exception.transforms)
    assert exception.property_line == 0
    value = render_program(_ground(SCALED, "scaled", "x * 2"),
                           InputSpec({"x": "int"}, {}, (), returns="int", postcondition="result > x"))
    assert "    return y + 1" in value.source
    assert not any(t.startswith("cut_after_suspect") for t in value.transforms)


def test_a_constructor_cannot_carry_a_value_oracle():
    grounded = replace(_ground(MAGNITUDE, "magnitude", "x if x > 0 else x"), entry="constructor")
    with pytest.raises(RenderError, match="constructor"):
        render_program(grounded, InputSpec({"x": "int"}, {}, ()))
