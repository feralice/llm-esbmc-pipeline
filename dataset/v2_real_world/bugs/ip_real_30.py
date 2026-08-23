def range_unsatisfiable_buggy(start_is_none: bool, end_is_none: bool, start: int, end: int, size: int) -> bool:
    if (not start_is_none) and start >= size:
        return True
    if end == 0:
        return True
    return False


def range_unsatisfiable_fixed(start_is_none: bool, end_is_none: bool, start: int, end: int, size: int) -> bool:
    if (not start_is_none) and (start >= size or ((not end_is_none) and start >= end)):
        return True
    if end == 0:
        return True
    return False


def main() -> None:
    start_is_none: bool = False
    end_is_none: bool = False
    start: int = 5
    end: int = 3
    size: int = 100
    buggy: bool = range_unsatisfiable_buggy(start_is_none, end_is_none, start, end, size)
    correct: bool = range_unsatisfiable_fixed(start_is_none, end_is_none, start, end, size)
    assert buggy == correct


main()
