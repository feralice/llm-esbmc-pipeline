def checked_positive(x: int) -> int:
    if x <= 0:
        return 0
    assert x > 0
    return x