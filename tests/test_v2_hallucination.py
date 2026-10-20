import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "v2_hallucination", Path(__file__).resolve().parents[1] / "scripts/v2_hallucination.py")
v2_hallucination = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2_hallucination)
check = v2_hallucination.check

SOURCE = '''def ratio(items, k):
    total = sum(items)
    first = items[0]
    return total / k
'''


def _c(expression, prop="", function="ratio"):
    return {"function": function, "expression": expression, "violated_property": prop, "note": ""}


def test_a_grounded_hypothesis_with_a_matching_operation_is_clean():
    assert check(_c("total / k", "ZeroDivisionError quando k == 0"), SOURCE) == []
    assert check(_c("items[0]", "IndexError com items vazio"), SOURCE) == []


def test_an_invented_function_is_flagged():
    assert check(_c("total / k", function="average"), SOURCE) == ["funcao_inexistente"]


def test_an_expression_not_in_the_code_is_flagged():
    assert check(_c("total // len(items)", "ZeroDivisionError"), SOURCE) == ["expressao_inexistente"]


def test_an_exception_the_operation_cannot_raise_is_flagged():
    assert check(_c("items[0]", "ZeroDivisionError em items[0]"), SOURCE) == ["excecao_incompativel"]
    assert check(_c("total / k", "IndexError em total / k"), SOURCE) == ["excecao_incompativel"]


def test_a_call_may_raise_anything_from_inside():
    code = "def f(cls, code, data, cols):\n    msg = getattr(cls, code)\n    return data.set_index(cols)\n"
    assert check(_c("getattr(cls, code)", "AttributeError", "f"), code) == []
    assert check(_c("data.set_index(cols)", "KeyError com cols None", "f"), code) == []


def test_the_prompt_rename_does_not_count_as_hallucination():
    recursive = "def walk(n):\n    return walk(n - 1) / n\n"
    assert check(_c("target_function(n - 1) / n", "ZeroDivisionError", "walk"), recursive) == []


def test_an_unchecked_exception_kind_is_not_judged():
    assert check(_c("sum(items)", "TypeError se items tiver None"), SOURCE) == []
