def safe_mod(value: int, scale: int) -> int:
    if scale == 0:
        return value
    return value % scale
