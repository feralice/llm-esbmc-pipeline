# mypy: disable-error-code=name-defined
from typing import List


def analyze_me(values: List[int], idx: int, denom: int) -> int:
    assert (0 <= (idx)) and ((idx) < len(values)), "out_of_bounds"
    item = values[idx]
    return item // denom


def main() -> None:
    values: List[int] = [10, 20, 30]
    idx: int = 1
    denom: int = 2
    result = analyze_me(values, idx, denom)
    assert result >= 0



def __esbmc_driver__() -> None:
    values = [nondet_int(), nondet_int(), nondet_int()]
    idx = nondet_int()
    denom = nondet_int()
    analyze_me(values, idx, denom)

__esbmc_driver__()
