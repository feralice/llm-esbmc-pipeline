from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.grounding import Grounded, GroundingFailure, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.levels import CONTEXT, limit_group

SOURCE = '''import math


def helper(x):
    return x * 2


def ratio(total, count):
    if count > 10:
        return total / count
    return total / count


class Tracker:
    depth: int

    def __init__(self, mode, cfg):
        self.mode = mode
        self.previous_defs = cfg.load()

    def _top(self):
        return self.previous_defs[-1]

    def maybe(self, depth: int):
        while self.previous_defs and self._top() >= depth:
            self.previous_defs.pop()
        return helper(self.mode)

    def unrelated(self):
        return self.other
'''


def _h(function, expression, line=0):
    return BugHypothesis(file="x.py", function=function, suspect_expression=expression, line=line)


def test_hypothesis_id_is_stable_and_depends_on_location():
    first = _h("ratio", "total / count", 11)
    assert first.hypothesis_id == _h("ratio", "total / count", 11).hypothesis_id
    assert first.hypothesis_id != _h("ratio", "total / count", 12).hypothesis_id


def test_from_candidate_keeps_expression_and_category():
    candidate = Candidate(file="a.py", function="f", category="none_misuse", expression="u.name", note="u may be None")
    h = BugHypothesis.from_candidate(candidate, line=7)
    assert (h.file, h.function, h.suspect_expression, h.line, h.category) == ("a.py", "f", "u.name", 7, "none_misuse")
    assert h.trigger_condition == "u may be None"


def test_missing_expression_is_a_grounding_failure():
    result = ground(_h("ratio", "total // count"), SOURCE)
    assert isinstance(result, GroundingFailure)
    assert "not found" in result.reason


def test_missing_function_is_a_grounding_failure():
    assert isinstance(ground(_h("nope", "total / count"), SOURCE), GroundingFailure)


def test_repeated_expression_picks_occurrence_nearest_to_line():
    result = ground(_h("ratio", "total / count", line=11), SOURCE)
    assert isinstance(result, Grounded)
    assert result.spans == ((11, 11),)
    assert result.function_start == 8


def test_repeated_expression_without_line_keeps_every_occurrence():
    result = ground(_h("ratio", "total / count"), SOURCE)
    assert isinstance(result, Grounded)
    assert result.spans == ((10, 10), (11, 11))


def test_free_function_params_and_verbatim_module():
    result = ground(_h("ratio", "total / count", 11), SOURCE)
    assert result.class_name is None
    assert [(p.name, p.annotation) for p in result.params] == [("total", None), ("count", None)]
    assert "def ratio(total, count):\n    if count > 10:\n        return total / count" in result.module
    assert "class Tracker" not in result.module


def test_method_collects_receiver_attributes_through_self_calls():
    result = ground(_h("Tracker.maybe", "self.previous_defs.pop()"), SOURCE)
    assert isinstance(result, Grounded)
    assert (result.class_name, result.method_name) == ("Tracker", "maybe")
    assert [(p.name, p.annotation) for p in result.params] == [("depth", "int")]
    assert result.receiver_attrs == ("mode", "previous_defs")
    assert "helper" in result.module and "def helper" in result.module


def test_decorators_are_blanked_and_recorded():
    source = "from app import for_app\n\n\n@for_app('php')\ndef match(command):\n    return command.split()[1]\n"
    result = ground(_h("match", "command.split()[1]"), source)
    assert isinstance(result, Grounded) and result.unsupported == ""
    assert "for_app" not in result.module
    assert result.transforms == ("decorators_removed:for_app('php')",)
    assert result.function_start == 5


def test_keyword_only_and_star_args_are_supported():
    source = "def f(a, *args, key, **kwargs):\n    return a // key\n"
    result = ground(_h("f", "a // key"), source)
    assert result.unsupported == ""
    assert [(p.name, p.keyword) for p in result.params] == [("a", False), ("key", True)]


def test_method_without_receiver_argument_is_unsupported():
    source = "class K:\n    def make():\n        return 1 // 0\n"
    assert ground(_h("K.make", "1 // 0"), source).unsupported


PROPERTY_SOURCE = '''class Request:
    def _get_url(self):
        return self._url

    url = property(_get_url)

    @property
    def body(self):
        return self._body

    def follow(self, n):
        return self.url[n] + self.body
'''


def test_properties_become_receiver_attributes():
    result = ground(_h("Request.follow", "self.url[n]"), PROPERTY_SOURCE)
    assert isinstance(result, Grounded) and result.unsupported == ""
    assert {"url", "body"} <= set(result.receiver_attrs)
    assert "property(" not in result.module and "@property" not in result.module
    assert "properties_as_attributes:body,url" in result.transforms


def test_property_getter_as_target_keeps_its_body():
    result = ground(_h("Request.body", "self._body"), PROPERTY_SOURCE)
    assert isinstance(result, Grounded)
    assert "def body(self):" in result.module
    assert result.receiver_attrs == ("_body",)


SETTER_SOURCE = '''class Box:
    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = int(value)

    size = property(lambda self: self._size, lambda self, v: None)

    def bump(self, v):
        self.x = v
        return self._x + 1 + self.size
'''


def test_property_with_a_setter_the_class_assigns_is_not_replaced():
    result = ground(_h("Box.bump", "self._x + 1"), SETTER_SOURCE)
    assert isinstance(result, Grounded)
    assert "x" not in result.receiver_attrs
    assert "@x.setter" in result.module
    assert "size" in result.receiver_attrs


NESTED = """def add_codes(err_cls):
    class ErrorsWithCodes(object):
        def __getattribute__(self, code):
            return getattr(err_cls, code)
    return ErrorsWithCodes()
"""


def test_method_of_a_class_defined_inside_a_function_is_unsupported_not_missing():
    h = BugHypothesis("a.py", "add_codes.ErrorsWithCodes.__getattribute__", "getattr(err_cls, code)")

    failure = ground(h, NESTED)

    assert isinstance(failure, GroundingFailure)
    assert failure.unsupported
    assert limit_group("UNSUPPORTED", failure.reason) == CONTEXT


def test_a_wrong_name_under_a_real_function_is_still_missing():
    h = BugHypothesis("a.py", "add_codes.ErrorsWithCodes.other", "getattr(err_cls, code)")

    failure = ground(h, NESTED)

    assert isinstance(failure, GroundingFailure)
    assert not failure.unsupported


HEADERS = """def check(required, k, params, y):
    if required and k not in params:
        return 1 // len(params)
    cur = params.get(k); val = cur + 1
    return y.shape[1]
"""


def test_a_suspect_copied_with_its_block_header_or_semicolon_still_grounds():
    for copied in ("if required and k not in params:", "return 1 // len(params)",
                   "cur = params.get(k); val = cur + 1"):
        assert isinstance(ground(BugHypothesis("a.py", "check", copied), HEADERS), Grounded), copied


def test_a_suspect_that_is_not_in_the_function_still_fails_after_the_rewrites():
    assert isinstance(ground(BugHypothesis("a.py", "check", "if k in params:"), HEADERS), GroundingFailure)
