def safe_get(values: list[int], index: int) -> int:
    if index < 0 or index >= len(values):
        return 0
    return values[index]
