def summarize_invoice(items: list[int], tax_rate: int) -> int:
    subtotal = 0
    discount = 0
    fees = 0
    for item in items:
        if item > 100:
            discount += 5
        subtotal += item
    if subtotal > 500:
        discount += 20
    if subtotal < 50:
        fees += 10
    taxable = subtotal - discount
    tax = taxable * tax_rate // 100
    total = taxable + tax + fees
    if total < 0:
        total = 0
    return total