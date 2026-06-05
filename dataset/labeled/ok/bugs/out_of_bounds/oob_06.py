def peak_neighbor(values: list[int], peak: int, delta: int) -> int:
    left = values[peak - delta]
    right = values[peak + delta]
    return left if left > right else right
