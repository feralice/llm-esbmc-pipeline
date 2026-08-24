def get_linewidth_buggy(linewidths_is_none: bool, user_value: int) -> int:
    return 1


def get_linewidth_correct(linewidths_is_none: bool, user_value: int) -> int:
    if linewidths_is_none:
        return 1
    return user_value


def main() -> None:
    linewidths_is_none: bool = nondet_bool()
    user_value: int = nondet_int()
    __ESBMC_assume(user_value >= 0 and user_value <= 20)
    buggy: int = get_linewidth_buggy(linewidths_is_none, user_value)
    correct: int = get_linewidth_correct(linewidths_is_none, user_value)
    assert buggy == correct


main()
