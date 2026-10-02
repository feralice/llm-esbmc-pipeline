def guarded_average(a: int, b: int) -> int:
    if a < 0 or b < 0:
        return 0
    return (a + b) // 2
