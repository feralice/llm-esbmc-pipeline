def guarded_next_value(values: list[int], index: int) -> int:
    next_index = index + 1
    if next_index < 0 or next_index >= len(values):
        return 0
    return values[next_index]