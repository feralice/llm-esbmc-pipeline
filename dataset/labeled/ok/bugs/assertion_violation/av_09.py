def branch_assertion(amount: int, flag: bool) -> int:
    if flag:
        return amount
    assert amount > 0
    return amount