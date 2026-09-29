from research_pipeline.scan.pipeline import ScanCandidate
from research_pipeline.verify.grounding import Grounded, GroundingFailure, ground
from research_pipeline.verify.hypothesis import BugHypothesis

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
    candidate = ScanCandidate(file="a.py", function="f", category="none_misuse", expression="u.name", note="u may be None")
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
