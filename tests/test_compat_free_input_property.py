"""A marked assert over unconstrained inputs proves nothing about the code.

The rejected harnesses are shapes the synthesizer produced in real V2 runs
(artifacts/v2/*/v2_checkpoint.json, 2026-09-28): ESBMC reported them as
confirmed only because it could pick any value for a free input.
"""
from __future__ import annotations

import pytest

from research_pipeline.scan.compat import VERDICT_INVALID, check_harness

FLAG_ONLY = '''
def model() -> None:
    server_name_is_none: bool = nondet_bool()
    assert not server_name_is_none, "LLM_ESBMC_EXPECTED_PROPERTY"


def main() -> None:
    model()


main()
'''

MAGNITUDE_BOUND_ONLY = '''
def model_getitem(index: int) -> int:
    __ESBMC_assume(abs(index) <= 1000)
    assert index >= 0, "LLM_ESBMC_EXPECTED_PROPERTY"
    return index


def main() -> None:
    index: int = nondet_int()
    model_getitem(index)


main()
'''

FREE_STRING_BEFORE_REAL_CALL = '''
def model(raw_val: str) -> float:
    assert raw_val != "", "LLM_ESBMC_EXPECTED_PROPERTY"
    converted: float = float(raw_val)
    return converted


def main() -> None:
    raw_val: str = nondet_str()
    model(raw_val)


main()
'''

COMPUTED_DIVISOR = '''
def model(a: int, b: int) -> float:
    divisor: int = b - a
    assert divisor != 0, "LLM_ESBMC_EXPECTED_PROPERTY"
    return 1.0 / divisor


def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    model(a, b)


main()
'''

REAL_CALLER_PRECONDITION = '''
def rating_ratio(not_parsed: int, num_substrings: int) -> float:
    assert num_substrings != 0, "LLM_ESBMC_EXPECTED_PROPERTY"
    return float(not_parsed) / float(num_substrings)


def main() -> None:
    not_parsed: int = nondet_int()
    num_substrings: int = nondet_int()
    __ESBMC_assume(not_parsed >= 0)
    __ESBMC_assume(not_parsed <= num_substrings)
    rating_ratio(not_parsed, num_substrings)


main()
'''

CONCRETE_ARGUMENT = '''
def first(size: int) -> int:
    assert size > 0, "LLM_ESBMC_EXPECTED_PROPERTY"
    return size


def main() -> None:
    first(0)


main()
'''


# Parameters of the real functions these shapes came from: none of the asserted
# stand-ins (server_name_is_none, index, raw_val) is one of them.
REAL_INPUTS = frozenset({"view_name", "kwargs", "config", "val", "floatfmt"})


@pytest.mark.parametrize("harness", [FLAG_ONLY, MAGNITUDE_BOUND_ONLY, FREE_STRING_BEFORE_REAL_CALL])
def test_assert_over_free_inputs_is_rejected(harness: str) -> None:
    result = check_harness(harness, category="native_runtime", real_inputs=REAL_INPUTS)
    assert result.verdict == VERDICT_INVALID
    assert any("unconstrained" in reason for reason in result.reasons)


@pytest.mark.parametrize("harness", [COMPUTED_DIVISOR, REAL_CALLER_PRECONDITION, CONCRETE_ARGUMENT])
def test_assert_grounded_in_code_or_preconditions_is_kept(harness: str) -> None:
    assert check_harness(harness, category="native_runtime", real_inputs=REAL_INPUTS).ok


def test_free_real_parameter_is_a_faithful_model() -> None:
    """`def f(x): return 10 // x` really accepts any x, so a free x is not a stand-in."""
    harness = FREE_STRING_BEFORE_REAL_CALL
    assert check_harness(harness, category="native_runtime", real_inputs=frozenset({"raw_val"})).ok


def test_rule_is_off_without_real_function_context() -> None:
    assert check_harness(FLAG_ONLY, category="native_runtime").ok
