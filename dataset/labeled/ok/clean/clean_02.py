def safe_difference(a: int, b: int, limit: int) -> int:
    diff = a - b
    if diff < 0:
        return 0
    if diff > limit:
        return limit
    return diff
