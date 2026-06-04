def compute_shipping(weight: int, distance: int, priority: bool) -> int:
    cost = 5
    if weight > 10:
        cost += 10
    if weight > 50:
        cost += 25
    if distance > 100:
        cost += 8
    if distance > 1000:
        cost += 40
    if priority:
        cost *= 2
    if cost < 0:
        cost = 0
    if cost > 1000:
        cost = 1000
    return cost