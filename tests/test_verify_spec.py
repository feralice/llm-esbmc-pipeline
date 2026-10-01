import pytest

from research_pipeline.verify.grounding import Grounded, Param
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.spec import (
    InputSpec,
    TypeShape,
    ignored_keys,
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
        ("Optional[None]", T("none")),
        ("set[int]", T("set", T("int"))),
        ("FrozenSet[str]", T("frozenset", T("str"))),
        ("list[set[str]]", T("list", T("set", T("str")))),
    ],
)
def test_parse_type_accepts_the_supported_subset(text, shape):
    assert parse_type(text) == shape


@pytest.mark.parametrize("text", ["dict[float, int]", "Foo", "Callable[[int], int]", "Optional[Foo]", "tuple[list[int]]",
                                  "int |", "int | str", "set[list[int]]", "set[Optional[int]]", "list[list[list[list[int]]]]", "type", "Optional[Optional[int]]"])
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


def test_unknown_names_are_ignored_not_rejected():
    grounded = _grounded(params=[Param("a", "int")])
    spec = InputSpec({"zz": "int"}, {"yy": "int"}, (), {"lib.nope": "int"})
    assert spec_problems(spec, grounded) == []
    assert ignored_keys(spec, grounded) == ["param zz", "attribute yy", "stub lib.nope"]


def test_misspelled_name_still_leaves_the_real_one_missing():
    grounded = _grounded(params=[Param("a", None)])
    assert spec_problems(InputSpec({"aa": "int"}, {}, ()), grounded) == ["parameter 'a': missing type"]


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


def test_assumption_may_use_membership_in_constants_and_fields_of_object_inputs():
    from research_pipeline.verify.grounding import ground
    from research_pipeline.verify.render import render_program
    source = """class Cron:
    def __init__(self, cron, line):
        self.cron = cron
        self.line = line

    def at(self, idx: int, start):
        if start.method == "HEAD":
            return self.cron.RANGES[idx]
        return 0
"""
    grounded = ground(BugHypothesis("x.py", "Cron.at", "self.cron.RANGES[idx]"), source)
    good = InputSpec({"start": "object"}, {"cron": "object"},
                     ("len(self.cron.RANGES) > idx", "start.method in ('HEAD', 'GET')", "idx not in (1, 2)"),
                     {"self.cron.RANGES": "list[int]", "start.method": "str"})
    assert spec_problems(good, grounded) == []
    program = render_program(grounded, good)
    assert "    __ESBMC_assume(len(_receiver.cron.RANGES) > idx)" in program.source
    assert "    __ESBMC_assume(start.method in ('HEAD', 'GET'))" in program.source
    bad = InputSpec({"start": "object"}, {"cron": "object"},
                    ("start.other == 1", "idx in (n, 2)", "start.method in [1]"),
                    {"self.cron.RANGES": "list[int]", "start.method": "str"})
    assert [p.split(" reads")[0].split(" may")[0].split(" uses")[0] for p in spec_problems(bad, grounded)] == [
        "assumption 'start.other == 1'", "assumption 'idx in (n, 2)'", "assumption 'start.method in [1]'"]
