from typing import List


def safe_get(lst: List[int], i: int) -> int:
    if not lst or i < 0 or i >= len(lst):
        return -1
    return lst[i]
