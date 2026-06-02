"""Expected: violation_found — out-of-bounds list access."""
from typing import List


def get_element(items: List[int], index: int) -> int:
    return items[index]


def main() -> None:
    data: List[int] = [1, 2, 3]
    idx: int = 5
    result: int = get_element(data, idx)


main()
