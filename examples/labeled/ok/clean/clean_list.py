def safe_first(items: list) -> object:
    if not items:
        return None
    return items[0]


def safe_pop(items: list, index: int) -> object:
    if 0 <= index < len(items):
        return items.pop(index)
    return None
