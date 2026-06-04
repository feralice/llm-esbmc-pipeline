def guarded_shifted_denominator(total: int, count: int) -> int:
    if count == 1:
        return total
    return total // (count - 1)