def guarded_negative_only(total: int, count: int) -> int:
    if count < 0:
        return 0
    return total // count