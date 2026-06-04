def is_valid_transition(state: int, target: int, locked: bool, admin: bool) -> bool:
    if locked and not admin:
        return False
    return (state == 0 and target in [1, 2]) or (state == 1 and target == 2) or (admin and target >= 0)