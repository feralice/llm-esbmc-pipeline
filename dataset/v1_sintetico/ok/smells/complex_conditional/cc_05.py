def choose_strategy(size: int, retries: int, cached: bool, urgent: bool) -> int:
    if (urgent and retries < 2) or (cached and size < 100) or (size > 1000 and retries == 0):
        return 1
    if (not urgent and cached) or (retries > 5 and size < 500):
        return 2
    return 3