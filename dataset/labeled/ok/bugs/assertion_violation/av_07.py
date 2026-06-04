def upper_limit_check(value: int, limit: int) -> int:
    if limit > 0:
        assert value < limit
    return value