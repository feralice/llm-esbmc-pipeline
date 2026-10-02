def modulo_non_negative_only(value: int, mod: int) -> int:
    if mod < 0:
        return value
    return value % mod