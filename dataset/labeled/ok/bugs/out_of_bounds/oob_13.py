def inclusive_upper_bound(values: list[int], index: int) -> int:
    if index <= len(values):
        return values[index]
    return 0