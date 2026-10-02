def guarded_large_denominator(total: int, denominator: int) -> int:
    if denominator > 10:
        return denominator
    return total // denominator