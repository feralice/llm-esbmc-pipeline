from pathlib import Path

from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.report import evaluate_verify, summarize

GT = Path("dataset/v2_real_world/ground_truths.json")
DETECTION = Path("dataset/v2_real_world/detection/av_real_01.py")


def _result(verdict, llm_calls, expression="assert isinstance(param, bool)", function="cli_bool_option"):
    return {"verdict": verdict, "llm_calls": llm_calls, "hypothesis": {
        "file": str(DETECTION), "function": function, "suspect_expression": expression, "category": "x"}}


def test_summarize_counts_verdicts_and_success_at_k():
    results = [_result("CONFIRMED", 1), _result("NOT_CONFIRMED", 2), _result("SPEC_FAILED", 3),
               _result("MISSING_DEPENDENCY", 0)]
    summary = summarize(results)
    assert summary["n"] == 4
    assert summary["by_verdict"]["CONFIRMED"] == 1 and summary["by_verdict"]["UNVALIDATED"] == 0
    assert summary["reached_llm"] == 3
    assert summary["success_at_k"] == {"1": 1 / 3, "2": 2 / 3, "3": 2 / 3}


def test_confirmed_hypothesis_at_the_true_location_counts_end_to_end():
    candidates = [Candidate(str(DETECTION), "cli_bool_option", "assertion_violation",
                                expression="assert isinstance(param, bool)")]
    evaluation = evaluate_verify([_result("CONFIRMED", 1)], candidates, GT, [DETECTION], [])
    assert evaluation["confirmed_by_location"]["expression"]["tp"] == 1
    assert evaluation["detection_by_location"]["expression"]["tp"] == 1


def test_unconfirmed_hypothesis_does_not_count_end_to_end():
    candidates = [Candidate(str(DETECTION), "cli_bool_option", "assertion_violation",
                                expression="assert isinstance(param, bool)")]
    evaluation = evaluate_verify([_result("UNVALIDATED", 1)], candidates, GT, [DETECTION], [])
    assert evaluation["confirmed_by_location"]["expression"]["tp"] == 0
