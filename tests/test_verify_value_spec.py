import pytest

from research_pipeline.verify.grounding import Grounded, Param
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.spec import (
    InputSpec,
    ignored_keys,
    parse_spec,
    shape_unpacked,
    spec_problems,
)


def _grounded(oracle=VALUE_ORACLE, receiver=False, params=("x", "xs")):
    return Grounded(
        hypothesis=BugHypothesis("x.py", "C.m" if receiver else "f", "x + 1", oracle=oracle),
        class_name="C" if receiver else None,
        method_name="m" if receiver else "f",
        spans=((2, 2),),
        params=tuple(Param(name, "int" if name == "x" else "list[int]") for name in params),
        receiver_attrs=("total",) if receiver else (),
        module="",
        attr_annotations={"total": "int"} if receiver else {},
        entry="method" if receiver else "function",
    )


def _spec(postcondition, returns="int"):
    return InputSpec({}, {}, (), returns=returns, postcondition=postcondition)


def test_parse_spec_reads_returns_and_postcondition():
    spec = parse_spec('{"params": {}, "returns": "int", "postcondition": "result >= 0"}')
    assert (spec.returns, spec.postcondition) == ("int", "result >= 0")
    assert parse_spec('{"params": {}}').postcondition == ""


def test_parse_spec_rejects_a_postcondition_that_is_not_a_string():
    with pytest.raises(ValueError):
        parse_spec('{"postcondition": ["result > 0"]}')


@pytest.mark.parametrize(("postcondition", "ok"), [
    ("result >= 0", True),
    ("len(result) <= len(xs)", True),
    ("isinstance(result, int)", True),
    ("result in ('a', 'b')", True),
    ("result is None or result > x", True),
    ("not (result == x + 1)", True),
    ("x > 0", False),
    ("result.strip() == ''", False),
    ("sorted(xs) == result", False),
    ("result[0] == 1", False),
    ("isinstance(result, Foo)", False),
    ("result > y", False),
    ("result in (x, 1)", False),
    ("result >", False),
])
def test_postcondition_language(postcondition, ok):
    problems = spec_problems(_spec(postcondition), _grounded(), require_property=True)
    assert (problems == []) is ok, problems


def test_receiver_attributes_are_the_state_after_the_call():
    grounded = _grounded(receiver=True)
    assert spec_problems(_spec("self.total >= 0", returns="None"), grounded, require_property=True) == []
    assert spec_problems(_spec("self.other >= 0", returns="None"), grounded, require_property=True) != []


def test_result_cannot_be_read_when_nothing_is_returned():
    problems = spec_problems(_spec("result >= 0", returns="None"), _grounded(), require_property=True)
    assert any("returns is None" in p for p in problems)


def test_value_hypotheses_need_both_fields_only_when_asked():
    assert spec_problems(InputSpec({}, {}, ()), _grounded()) == []
    problems = spec_problems(InputSpec({}, {}, ()), _grounded(), require_property=True)
    assert "returns: missing type" in problems and "postcondition: missing" in problems


def test_object_is_not_a_return_type():
    problems = spec_problems(_spec("result is not None", returns="object"), _grounded(), require_property=True)
    assert any(p.startswith("returns:") for p in problems)


def test_a_parameter_named_result_is_reported():
    problems = spec_problems(_spec("result >= 0"), _grounded(params=("x", "result")), require_property=True)
    assert any("named result" in p for p in problems)


def test_exception_hypotheses_ignore_the_value_fields():
    grounded = _grounded(oracle="")
    assert ignored_keys(_spec("x > 0"), grounded) == ["returns", "postcondition"]
    assert spec_problems(_spec("x > 0"), grounded) == []


def test_shape_unpacked_keeps_the_value_fields():
    spec = shape_unpacked(_spec("result >= 0"), _grounded())
    assert (spec.returns, spec.postcondition) == ("int", "result >= 0")


def _object_input():
    g = _grounded(params=("command",))
    return Grounded(**{**g.__dict__, "params": (Param("command", ""),),
                       "object_members": {"command": {"script": None}}})


def _object_spec(postcondition):
    return parse_spec('{"params": {"command": "object"}, "stubs": {"command.script": "str"}, '
                      f'"returns": "bool", "postcondition": "{postcondition}"}}')


def test_the_postcondition_may_read_a_field_of_an_object_input():
    spec = _object_spec("not result or command.script == 'ls'")
    assert spec_problems(spec, _object_input(), require_property=True) == []


def test_a_postcondition_over_input_fields_alone_is_rejected():
    problems = spec_problems(_object_spec("command.script == 'ls'"), _object_input(), require_property=True)
    assert any("reads neither result" in p for p in problems)


def test_a_field_the_spec_does_not_build_is_still_rejected():
    problems = spec_problems(_object_spec("not result or command.other == 'ls'"), _object_input(),
                             require_property=True)
    assert any("nor an input field" in p for p in problems)
