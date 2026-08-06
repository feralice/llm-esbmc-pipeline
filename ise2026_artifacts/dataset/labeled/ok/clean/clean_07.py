def safe_scale(value: int, factor: int, limit: int) -> int:
    if factor <= 0 or value < 0:
        return 0
    result = value * factor
    if result > limit:
        return limit
    return result
