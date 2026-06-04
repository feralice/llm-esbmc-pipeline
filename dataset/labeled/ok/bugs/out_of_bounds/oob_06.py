def guarded_next(values: list[int], index: int) -> int:
    if index < len(values):
        return values[index + 1]
    return 0