"""Cenário: bugs reais sem guardas — espera formally_confirmed_bug ou suspected_bug."""
from typing import List


def divide(a: int, b: int) -> float:
    return a / b


def get_element(items: List[int], index: int) -> int:
    return items[index]


def process(values: List[int], divisor: int) -> int:
    total = 0
    for v in values:
        total += v
    return total // divisor
