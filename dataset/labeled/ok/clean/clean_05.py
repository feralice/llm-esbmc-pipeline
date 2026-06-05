def safe_next(values: list[int], pos: int) -> int:
    next_pos = pos + 1
    if next_pos < 0 or next_pos >= len(values):
        return 0
    return values[next_pos]
