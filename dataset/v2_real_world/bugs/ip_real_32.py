def pm_hour_buggy(hour: int) -> int:
    return hour + 12


def pm_hour_correct(hour: int) -> int:
    h: int = hour + 12
    if h > 23:
        h -= 24
    return h


def main() -> None:
    hour: int = nondet_int()
    __ESBMC_assume(hour >= 1 and hour <= 12)
    buggy: int = pm_hour_buggy(hour)
    correct: int = pm_hour_correct(hour)
    assert 0 <= buggy <= 23
    assert buggy == correct


main()
