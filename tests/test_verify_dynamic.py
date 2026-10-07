from pathlib import Path

from research_pipeline.verify.dynamic import FUZZ_FOUND, FUZZ_NOTHING, FUZZ_UNAVAILABLE, dynamic_check

PROGRAM = (
    "def f(x: int) -> int:\n"
    "    return 10 // (x - 100)\n"
    "\n"
    "f(nondet_int())\n"
)


def _result(tmp_path: Path, source: str | None, expression: str = "10 // (x - 100)") -> dict:
    hypothesis = {"function": "f", "suspect_expression": expression, "hypothesis_id": "h"}
    if source is None:
        return {"hypothesis": hypothesis, "verdict": "GROUNDING_FAILED", "attempts": []}
    path = tmp_path / "h_a0.py"
    path.write_text(source)
    return {"hypothesis": hypothesis, "verdict": "UNSUPPORTED", "program_path": str(path), "attempts": [{}]}


def test_a_crash_at_the_hypothesis_line_is_fuzz_found(tmp_path: Path) -> None:
    outcome = dynamic_check(_result(tmp_path, PROGRAM), seed=1)
    assert outcome["verdict"] == FUZZ_FOUND and outcome["replay"]["exception_type"] == "ZeroDivisionError"


def test_nothing_found_in_the_budget(tmp_path: Path) -> None:
    safe = PROGRAM.replace("10 // (x - 100)", "10 // (abs(x) + 1)")
    assert dynamic_check(_result(tmp_path, safe, "10 // (abs(x) + 1)"), seed=1)["verdict"] == FUZZ_NOTHING


def test_no_program_is_unavailable(tmp_path: Path) -> None:
    assert dynamic_check(_result(tmp_path, None))["verdict"] == FUZZ_UNAVAILABLE
