from typing import List


def analyze_me(values: List[int], idx: int, denom: int) -> int:
    item = values[idx]
    return item // denom


def main() -> None:
    values: List[int] = [10, 20, 30]
    idx: int = 1
    denom: int = 2
    result = analyze_me(values, idx, denom)
    assert result >= 0


main()
