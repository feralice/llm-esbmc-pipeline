def process_customer_profile(name_code: int, address_code: int, phone_code: int, email_code: int, complaint_code: int) -> int:
    score = 0
    if name_code > 0:
        score += 1
    if address_code > 0:
        score += 1
    if phone_code > 0:
        score += 1
    if email_code > 0:
        score += 1
    if name_code > 0 and address_code > 0 and phone_code > 0 and email_code > 0:
        score += 2
    promo_sent = 1
    discount_sent = 1
    arrivals_sent = 1
    score += promo_sent + discount_sent + arrivals_sent
    if score > 6:
        score -= 3
    loyalty_points = score // 3
    score += loyalty_points
    if complaint_code == 1:
        score -= 3
    elif complaint_code == 2:
        score -= 2
    elif complaint_code == 3:
        score -= 1
    receipt_given = True
    if receipt_given:
        score += 1
    chained = score > 0
    if chained:
        score += 1
    middleman = chained and score > 1
    if middleman:
        score += 1
    if score < 0:
        score = 0
    return score
