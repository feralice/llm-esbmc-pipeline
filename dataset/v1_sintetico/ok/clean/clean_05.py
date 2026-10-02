def capped_increment(value: int, cap: int) -> int:
    if value >= cap:
        return cap
    return value + 1
