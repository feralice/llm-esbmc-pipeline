"""Expected: violation_found — division by zero at runtime."""
from typing import List


def compute_average(values: List[int], count: int) -> int:
    total: int = 0
    for v in values:
        total += v
    return total // count


def main() -> None:
    data: List[int] = [10, 20, 30]
    count: int = 0
    result: int = compute_average(data, count)


main()
