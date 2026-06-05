def shifted_by_length(values: list[int], start: int) -> int:
    offset = start + len(values)
    return values[offset]