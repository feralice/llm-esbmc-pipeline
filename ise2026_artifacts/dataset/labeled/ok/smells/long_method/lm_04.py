def tally_customer_complaints(cold: bool, late: bool, wrong_order: bool, burnt: bool, little_cheese: bool, undercooked: bool) -> int:
    complaints = 0
    if cold:
        complaints += 1
    if late:
        complaints += 1
    if wrong_order:
        complaints += 1
    if burnt:
        complaints += 1
    if little_cheese:
        complaints += 1
    if undercooked:
        complaints += 1
    severity = 0
    if cold:
        severity += 1
    if late:
        severity += 2
    if wrong_order:
        severity += 3
    if burnt:
        severity += 3
    if little_cheese:
        severity += 1
    if undercooked:
        severity += 2
    total_score = complaints * 2 + severity
    if complaints > 3:
        total_score += 5
    receipt_given = True
    if receipt_given:
        total_score += 1
    if total_score > 20:
        total_score = 20
    return total_score
