def checked_one_used_two(values: list[int], pos: int) -> int:
    if pos + 1 < len(values):
        return values[pos + 2]
    return 0