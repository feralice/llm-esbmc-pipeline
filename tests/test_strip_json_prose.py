from __future__ import annotations

import json

import pytest

from research_pipeline.llm.findings import strip_markdown_json


@pytest.mark.parametrize("text", [
    'Aqui está o resultado:\n{"a": 1}',
    'Resultado: {"a": 1}\nEspero ter ajudado.',
    '<think>x</think>\nSegue:\n```json\n{"a": 1}\n```',
])
def test_json_is_recovered_from_surrounding_prose(text: str) -> None:
    assert json.loads(strip_markdown_json(text)) == {"a": 1}


def test_text_without_json_is_left_for_the_caller_to_reject() -> None:
    with pytest.raises(json.JSONDecodeError):
        json.loads(strip_markdown_json("sem json aqui"))


@pytest.mark.parametrize("text", [
    '{"findings":[{"a":1},{"b":',
    '{"findings":[{"a":1},]}',
    '"a [1] b"',
])
def test_text_that_starts_like_json_is_never_replaced_by_a_nested_fragment(text: str) -> None:
    assert strip_markdown_json(text) == text.strip()


def test_prose_with_a_bracketed_number_does_not_hide_the_json_object() -> None:
    assert json.loads(strip_markdown_json('See x[0]: {"findings": []}')) == {"findings": []}
    assert json.loads(strip_markdown_json('Aqui [1] está: {"x": 1}')) == {"x": 1}
