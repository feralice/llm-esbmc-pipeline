def two_pointer_gap(values: list[int], left: int, right: int, gap: int) -> int:
    a = values[left]
    b = values[right + gap]
    return b - a
