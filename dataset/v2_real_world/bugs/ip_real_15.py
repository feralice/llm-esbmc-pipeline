def maybe_empty_lines_before(before: int, previous_after: int, is_first_line: bool) -> int:
    return before - previous_after


def maybe_empty_lines_before_fixed(before: int, previous_after: int, is_first_line: bool) -> int:
    if is_first_line:
        return 0
    return before - previous_after


def main() -> None:
    before: int = nondet_int()
    previous_after: int = nondet_int()
    is_first_line: bool = nondet_bool()
    __ESBMC_assume(before >= 0 and before <= 10)
    __ESBMC_assume(previous_after >= 0 and previous_after <= 10)
    buggy: int = maybe_empty_lines_before(before, previous_after, is_first_line)
    correct: int = maybe_empty_lines_before_fixed(before, previous_after, is_first_line)
    assert buggy == correct


main()
