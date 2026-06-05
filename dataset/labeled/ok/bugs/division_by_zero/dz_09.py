def conditional_zero_guard(total: int, divisor: int) -> int:
    if divisor == 0 and total > 0:
        return total
    return total // divisor