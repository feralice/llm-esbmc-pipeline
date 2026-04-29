from typing import List


def total(values: List[int]) -> int:
    return sum(v for v in values if v > 0)
