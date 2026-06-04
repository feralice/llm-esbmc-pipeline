def branch_assertion(amount: int, flag: bool) -> int:
    if flag:
        assert amount >= 0
    else:
        assert amount > 0
    return amount