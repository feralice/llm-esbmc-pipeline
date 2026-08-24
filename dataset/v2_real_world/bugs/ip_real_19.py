def keep_buggy(v: int) -> bool:
    return bool(v)


def keep_correct(v: int) -> bool:
    return True


def main() -> None:
    v: int = nondet_int()
    __ESBMC_assume(v >= 0 and v <= 999)
    assert keep_buggy(v) == keep_correct(v)


main()
