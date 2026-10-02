def off_by_one_denominator(total: int, count: int) -> int:
    if count < 1:
        return 0
    return total // (count - 1)