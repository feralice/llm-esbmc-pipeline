import pytest

from research_pipeline.verify.grounding import Grounded, Param
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.spec import (
    InputSpec,
    TypeShape,
    parse_spec,
    parse_type,
    spec_problems,
)


def _grounded(params=(), attrs=(), annotations=None, class_name="C"):
    return Grounded(
        hypothesis=BugHypothesis("x.py", "C.m", "a / b"),
        class_name=class_name,
        method_name="m",
        spans=((3, 3),),
        params=tuple(params),
        receiver_attrs=tuple(attrs),
        module="",
        attr_annotations=annotations or {},
        entry="method" if class_name else "function",
    )


T = TypeShape


@pytest.mark.parametrize(
    ("text", "shape"),
    [
        ("int", T("int")),
        ("str", T("str")),
        ("bytes", T("bytes")),
        ("object", T("object")),
        ("list[int]", T("list", T("int"))),
        ("List[str]", T("list", T("str"))),
        ("list[list[str]]", T("list", T("list", T("str")))),
        ("dict[str, int]", T("dict", T("int"), key="str")),
        ("Dict[int, list[str]]", T("dict", T("list", T("str")), key="int")),
        ("Optional[int]", T("int", optional=True)),
        ("int | None", T("int", optional=True)),
        ("Optional[list[float]]", T("list", T("float"), optional=True)),
        ("list[Optional[str]]", T("list", T("str", optional=True))),
        ("None", T("none")),
    ],
)
def test_parse_type_accepts_the_supported_subset(text, shape):
    assert parse_type(text) == shape


@pytest.mark.parametrize("text", ["dict[float, int]", "Foo", "Callable[[int], int]", "Optional[Foo]", "tuple[list[int]]",
                                  "int |", "int | str", "list[list[list[list[int]]]]", "type", "Optional[Optional[int]]"])
def test_parse_type_rejects_everything_else(text):
    assert parse_type(text) is None


def test_parse_spec_reads_the_three_fields():
    spec = parse_spec('{"params": {"b": "int"}, "attributes": {"xs": "list[int]"}, "assumptions": ["b >= 0"]}')
    assert spec == InputSpec({"b": "int"}, {"xs": "list[int]"}, ("b >= 0",))


def test_parse_spec_rejects_non_json():
    with pytest.raises(ValueError):
        parse_spec("here is the spec: {")


def test_annotated_params_need_no_spec_entry():
    grounded = _grounded(params=[Param("a", "int")])
    assert spec_problems(InputSpec({}, {}, ()), grounded) == []


def test_untyped_param_and_attribute_are_reported():
    grounded = _grounded(params=[Param("a", None)], attrs=["xs"])
    problems = spec_problems(InputSpec({}, {}, ()), grounded)
    assert any("parameter 'a'" in p for p in problems)
    assert any("attribute 'xs'" in p for p in problems)


def test_attribute_type_can_come_from_class_annotation():
    grounded = _grounded(attrs=["xs"], annotations={"xs": "list[int]"})
    assert spec_problems(InputSpec({}, {}, ()), grounded) == []


def test_unsupported_type_is_reported():
    grounded = _grounded(params=[Param("a", None)])
    problems = spec_problems(InputSpec({"a": "Callable"}, {}, ()), grounded)
    assert problems == ["parameter 'a': unsupported type 'Callable'"]


def test_unknown_names_are_reported():
    grounded = _grounded(params=[Param("a", "int")])
    problems = spec_problems(InputSpec({"zz": "int"}, {"yy": "int"}, ()), grounded)
    assert "unknown parameter 'zz'" in problems
    assert "unknown attribute 'yy'" in problems


@pytest.mark.parametrize(
    ("assumption", "ok"),
    [
        ("a >= 0 and a < 10", True),
        ("self.xs is not None", True),
        ("len(self.xs) > 0", True),
        ("b > 0", False),
        ("self.zz > 0", False),
        ("sorted(self.xs)", False),
        ("a = 1", False),
    ],
)
def test_assumptions_may_only_use_inputs_and_len(assumption, ok):
    grounded = _grounded(params=[Param("a", "int")], attrs=["xs"], annotations={"xs": "list[int]"})
    problems = spec_problems(InputSpec({}, {}, (assumption,)), grounded)
    assert (problems == []) is ok
