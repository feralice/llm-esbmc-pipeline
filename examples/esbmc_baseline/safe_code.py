"""Expected: no_violation_found — all operations guarded."""
from typing import List


def safe_divide(a: int, b: int) -> int:
    if b == 0:
        return 0
    return a // b


def safe_get(items: List[int], index: int) -> int:
    if index < 0 or index >= len(items):
        return -1
    return items[index]


def main() -> None:
    x: int = safe_divide(10, 2)
    data: List[int] = [1, 2, 3]
    y: int = safe_get(data, 1)
    assert x == 5
    assert y == 2


main()
