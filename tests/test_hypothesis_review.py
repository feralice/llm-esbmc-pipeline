from __future__ import annotations

import json

from research_pipeline.hypothesis_review import (
    ReviewScore,
    build_review_user_prompt,
    parse_review,
    review_candidates,
    split_by_threshold,
)
from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.llm_client import SynthResult

SOURCE = "def f(x, y):\n    return x // y\n"


def _candidate(expression: str = "x // y", function: str = "f", file: str = "a.py") -> Candidate:
    return Candidate(file=file, function=function, expression=expression)


def _answer(score: object = 8, guard_found: bool = False, feasible: bool = True) -> str:
    return json.dumps({"explanation": "no guard", "guard_found": guard_found, "feasible": feasible, "score": score})


class _FakeLLM:
    def __init__(self, text: str = "") -> None:
        self.text = text or _answer()
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> SynthResult:
        self.calls += 1
        return SynthResult(harness=self.text, raw_response=self.text, model="fake")


def test_parse_review_reads_a_valid_answer() -> None:
    review = parse_review(_answer(score=8, guard_found=False, feasible=True))
    assert review == ReviewScore(8.0, False, True, "no guard")


def test_parse_review_rejects_score_out_of_range_and_non_json() -> None:
    for text in ("not json", _answer(score=11), _answer(score=-1), _answer(score="8"), '{"score": 5}', "[]"):
        review = parse_review(text)
        assert review.score is None and review.error, text


def test_split_keeps_unscored_and_borderline() -> None:
    candidates = [_candidate("a"), _candidate("b"), _candidate("c"), _candidate("d")]
    scores = [ReviewScore(4.0, None, None, ""), ReviewScore(3.9, None, None, ""),
              ReviewScore(None, None, None, "", error="boom"), ReviewScore(9.0, None, None, "")]
    kept, dropped = split_by_threshold(candidates, scores, 4.0)
    assert [c.expression for c in kept] == ["a", "c", "d"]
    assert [c.expression for c, _ in dropped] == ["b"]


def test_review_candidates_uses_cache_and_scores_equal_expressions_once() -> None:
    llm, cache = _FakeLLM(), {}
    sources = {("a.py", "f"): SOURCE}
    candidates = [_candidate("x // y"), _candidate("x//y")]
    first = review_candidates(candidates, sources, llm, cache)
    assert llm.calls == 1 and [r.score for r in first] == [8.0, 8.0]
    again = review_candidates(candidates, sources, llm, cache)
    assert llm.calls == 1 and [r.score for r in again] == [8.0, 8.0]


def test_missing_source_keeps_candidate() -> None:
    llm = _FakeLLM()
    [review] = review_candidates([_candidate()], {}, llm, {})
    assert review.score is None and "function source not found" in review.error and llm.calls == 0


def test_an_invalid_answer_is_not_cached() -> None:
    llm, cache = _FakeLLM("garbage"), {}
    [review] = review_candidates([_candidate()], {("a.py", "f"): SOURCE}, llm, cache)
    assert review.score is None and cache == {}


def test_prompt_undoes_the_prompt_rename_and_marks_code_as_data() -> None:
    prompt = build_review_user_prompt(_candidate("target_function(x - 1)", function="Cls.f"), SOURCE)
    assert "f(x - 1)" in prompt and "target_function" not in prompt
    assert "UNTRUSTED" in prompt and SOURCE.strip() in prompt


def test_usage_limit_stops_the_pass_and_keeps_scores_already_cached() -> None:
    import pytest

    from research_pipeline.llm.rate_limit import UsageLimitReached

    class _Limit(_FakeLLM):
        def complete(self, *args, **kwargs):
            if self.calls:
                raise UsageLimitReached("limit")
            return super().complete(*args, **kwargs)

    cache: dict = {}
    candidates = [_candidate("x // y"), _candidate("y - 1")]
    with pytest.raises(UsageLimitReached):
        review_candidates(candidates, {("a.py", "f"): SOURCE}, _Limit(), cache)
    assert len(cache) == 1
