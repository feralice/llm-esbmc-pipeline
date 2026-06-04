def can_apply_discount(age: int, purchases: int, member: bool, blocked: bool) -> bool:
    return (member and purchases > 5 and not blocked) or (age > 65 and purchases > 1 and not blocked)