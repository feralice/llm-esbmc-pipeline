import pytest

from research_pipeline.verify.healing import (
    Patch,
    PatchError,
    apply_patch,
    patch_problems,
)

SOURCE = '''import os

from lib import helper


def target(x, items):
    total = helper(x)
    return items[total]
'''


def _problems(**patch):
    return patch_problems(SOURCE, Patch(**patch), "target")


def test_edit_must_match_once():
    with pytest.raises(PatchError, match="not found"):
        apply_patch(SOURCE, Patch(edits=(("nothing here", "x"),)))
    doubled = SOURCE + "\nitems = 1\nitems = 1\n"
    with pytest.raises(PatchError, match="2 times"):
        apply_patch(doubled, Patch(edits=(("items = 1", "items = 2"),)))


def test_definitions_appended_after_imports():
    patched = apply_patch(SOURCE, Patch(definitions="def helper(a=None) -> int:\n    return nondet_int()\n"))
    assert patched.index("from lib import helper") < patched.index("def helper") < patched.index("def target")


def test_target_body_change_is_rejected():
    assert any("target" in p for p in _problems(edits=(("return items[total]", "return items[0]"),)))


def test_signature_annotation_is_allowed():
    assert _problems(edits=(("def target(x, items):", "def target(x: int, items: list[int]):"),)) == []


@pytest.mark.parametrize("body", ["return []", "return 0", "return None"])
def test_stub_with_concrete_return_is_rejected(body):
    assert any("helper" in p for p in _problems(definitions=f"def helper(a=None) -> list:\n    {body}\n"))


def test_stub_returning_none_for_none_is_accepted():
    assert _problems(definitions="def log(a=None) -> None:\n    return None\n") == []


def test_stub_with_nondet_return_is_accepted():
    definitions = ("class Box:\n    def __init__(self) -> None:\n        self.n: int = nondet_int()\n\n"
                   "def helper(a=None) -> int:\n    return nondet_int()\n\n"
                   "def make(a=None) -> Box:\n    return Box()\n")
    assert _problems(definitions=definitions) == []


def test_stub_class_field_with_fixed_value_is_rejected():
    definitions = "class Box:\n    def __init__(self) -> None:\n        self.n: int = 0\n"
    assert _problems(definitions=definitions) != []


@pytest.mark.parametrize("line", ["raise ValueError('x')", "assert a"])
def test_stub_with_raise_or_assert_is_rejected(line):
    definitions = f"def helper(a=None) -> int:\n    {line}\n    return nondet_int()\n"
    assert any("helper" in p for p in _problems(definitions=definitions))


def test_patch_that_breaks_parsing_is_rejected():
    assert _problems(real_code="def broken(:\n") == ["the patched source does not parse"]


def test_real_code_from_the_graph_is_not_held_to_stub_rules():
    assert _problems(real_code="def helper(a):\n    return []\n") == []


def test_unappliable_edit_is_a_problem_not_a_crash():
    assert _problems(edits=(("nope", "x"),)) == ["edit text not found: 'nope'"]
