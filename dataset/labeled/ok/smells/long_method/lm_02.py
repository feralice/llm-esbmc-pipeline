def classify_order(quantity: int, price: int, region: int) -> int:
    score = 0
    if quantity > 10:
        score += 2
    if quantity > 100:
        score += 5
    if price > 50:
        score += 3
    if region == 1:
        score += 1
    if region == 2:
        score += 2
    if score > 8:
        return 3
    if score > 4:
        return 2
    return 1