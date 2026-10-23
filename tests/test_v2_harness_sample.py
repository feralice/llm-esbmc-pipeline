import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from v2_harness_sample import harness_sample  # noqa: E402

from research_pipeline.verify.hypothesis import VALUE_ORACLE  # noqa: E402

ITEMS = {f"b{n}": {"id": f"b{n}", "function": "f", "expression": "x / y"} for n in range(6)}


def _result(bug: str, hid: str, *, expression: str = "x / y", oracle: str = "") -> dict:
    return {"hypothesis": {"file": f"dataset/{bug}.py", "function": "f", "suspect_expression": expression,
                           "line": 0, "trigger_condition": "y is 0", "category": "", "oracle": oracle,
                           "hypothesis_id": hid}, "verdict": "CONFIRMED"}


def _results() -> list[dict]:
    return [_result(f"b{n}", f"h{n}{k}") for n in range(6) for k in range(2)]


def _ids(sample: list[dict]) -> list[str]:
    return [h["hypothesis_id"] for h in sample]


def test_sample_is_deterministic_for_a_seed():
    assert _ids(harness_sample(_results(), ITEMS, 4, 7)) == _ids(harness_sample(list(reversed(_results())), ITEMS, 4, 7))


def test_sample_keeps_only_at_line_exception_hypotheses():
    results = [_result("b0", "off", expression="z + 1"), _result("b1", "val", oracle=VALUE_ORACLE),
               _result("b2", "ok")]
    assert _ids(harness_sample(results, ITEMS, 10, 1)) == ["ok"]


def test_one_hypothesis_per_bug():
    sample = harness_sample(_results(), ITEMS, 10, 1)
    assert len(sample) == 6
    assert len({h["bug"] for h in sample}) == 6
