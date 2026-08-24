def expand_month_step(month: int, step: int) -> int:
    return month % step


def expand_month_step_fixed(month: int, step: int) -> int:
    return ((month - 1) % step) + 1


def main() -> None:
    month: int = nondet_int()
    step: int = nondet_int()
    __ESBMC_assume(month >= 1 and month <= 12)
    __ESBMC_assume(step >= 1 and step <= 12)
    buggy: int = expand_month_step(month, step)
    correct: int = expand_month_step_fixed(month, step)
    assert buggy == correct


main()
