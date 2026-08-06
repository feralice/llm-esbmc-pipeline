def process_cashier_workflow(order_code: int, chef_busy: bool, customer_upset: bool, distance: int) -> int:
    total = 0
    if order_code == 1:
        total += 8
    elif order_code == 2:
        total += 12
    else:
        total += 6
    if chef_busy:
        total -= 1
        hurried = True
    else:
        hurried = False
    if hurried:
        total += 1
    if customer_upset:
        calmed = True
        total -= 2
    else:
        calmed = False
    if calmed:
        total += 1
    delivered = False
    if distance <= 5:
        total += 3
        delivered = True
    elif distance <= 15:
        total += 1
        delivered = True
    if delivered:
        total += 1
    receipt_given = total > 0
    if receipt_given:
        total += 1
    if total < 0:
        total = 0
    return total
