def process_pizza_order(pizza_type: int, size: int, has_discount_code: bool, complaint_code: int) -> int:
    status = 0
    if pizza_type == 1:
        status += 10
    elif pizza_type == 2:
        status += 15
    else:
        status += 5
    status += 1
    if size > 2:
        status += 3
    delivered = status > 0
    if delivered:
        status += 2
    hurried = size > 3
    if hurried:
        status += 1
    kitchen_clean = True
    if kitchen_clean:
        status += 1
    if has_discount_code:
        status -= 5
    notified = 0
    notified += 1
    notified += 1
    notified += 1
    status += notified
    loyalty_points = status // 10
    status += loyalty_points
    if complaint_code == 1:
        status -= 3
    elif complaint_code == 2:
        status -= 4
    elif complaint_code == 3:
        status -= 2
    else:
        status -= 1
    if status < 0:
        status = 0
    return status
