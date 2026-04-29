# mypy: disable-error-code=name-defined
from typing import List


def analyze_me(values: List[int], idx: int, denom: int) -> int:
    item = values[idx]
    assert (denom) != 0, "division_by_zero"
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
    __ESBMC_assume((0 <= (idx)) and ((idx) < len(values)))
    analyze_me(values, idx, denom)

__esbmc_driver__()
