def buggy_range_not_satisfiable(start: int, has_start: bool, end: int, has_end: bool, size: int) -> bool:
    # Real code (tornado/web.py:StaticFileHandler, BugsInPy tornado bug #4):
    # negative `start` was clamped to a non-negative offset AFTER the
    # satisfiability check ran, so a negative start that clamps into a valid
    # range still tripped a false 416, and `start >= end` was never checked at
    # all.
    s: int = start
    condition: bool = (has_start and s >= size) or (has_end and end == 0)
    return condition


def correct_range_not_satisfiable(start: int, has_start: bool, end: int, has_end: bool, size: int) -> bool:
    # Fix clamps negative start BEFORE the check, and also rejects start >= end.
    s: int = start
    if has_start and s < 0:
        s = s + size
        if s < 0:
            s = 0
    condition: bool = (has_start and (s >= size or (has_end and s >= end))) or (has_end and end == 0)
    return condition


def main() -> None:
    start: int = nondet_int()
    end: int = nondet_int()
    has_start: bool = nondet_bool()
    has_end: bool = nondet_bool()
    size: int = nondet_int()
    __ESBMC_assume(size > 0)
    __ESBMC_assume(start > -1000 and start < 1000)
    __ESBMC_assume(end > -1000 and end < 1000)

    buggy: bool = buggy_range_not_satisfiable(start, has_start, end, has_end, size)
    correct: bool = correct_range_not_satisfiable(start, has_start, end, has_end, size)
    assert buggy == correct


main()
