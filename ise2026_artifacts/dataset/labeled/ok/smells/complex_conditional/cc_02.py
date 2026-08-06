def evaluate_access(active: bool, verified: bool, role: int, level: int) -> bool:
    if active:
        if verified:
            if role >= level:
                if level > 5:
                    return role > 8
                return True
            return False
        return False
    return False
