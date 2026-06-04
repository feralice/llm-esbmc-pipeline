def guarded_but_too_weak(x: int) -> int:
    if x >= 0:
        assert x > 10
    return x