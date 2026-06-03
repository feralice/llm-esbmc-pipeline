def safe_divide(a: int, b: int) -> float:
    if b == 0:
        return 0.0
    return a / b
