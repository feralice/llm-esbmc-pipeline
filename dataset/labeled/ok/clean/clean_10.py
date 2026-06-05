def guarded_second(values: list[int]) -> int:
    if len(values) <= 1:
        return 0
    return values[1]