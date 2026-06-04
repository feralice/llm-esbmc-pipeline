def calculate_quote(base: int, tax: int, fee: int, discount: int, region: int, priority: bool) -> int:
    total = base + tax + fee + region
    if priority:
        total += 10
    return total - discount