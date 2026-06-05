def high_low_scale(high: int, low: int) -> int:
    denom = high - low
    return 100 // denom