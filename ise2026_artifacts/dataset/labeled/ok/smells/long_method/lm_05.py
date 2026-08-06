def finalize_detailed_order(pizza_type: int, size: int, extra_cheese: bool, has_contact_info: bool, has_discount_code: bool) -> int:
    total = 0
    if pizza_type == 1:
        total += 9
    elif pizza_type == 2:
        total += 11
    elif pizza_type == 3:
        total += 7
    else:
        total += 5
    if size > 2:
        total += 3
    if extra_cheese:
        total += 2
    if has_contact_info:
        total += 2
        contact_updated = True
    else:
        contact_updated = False
    if contact_updated:
        total += 1
    if has_discount_code:
        total -= 3
        discount_applied = True
    else:
        discount_applied = False
    if discount_applied:
        total += 1
    loyalty_points = total // 4
    total += loyalty_points
    if total < 0:
        total = 0
    if total > 30:
        total = 30
    return total
