def wcswidth_loop(pwcs: list, n: int) -> int:
    end: int = n
    width: int = 0
    i: int = 0
    while i < end:
        width += pwcs[i]
        i += 1
    return width


def main() -> None:
    m: int = nondet_int()
    __ESBMC_assume(m >= 0 and m <= 5)
    pwcs: list = [1] * m
    n: int = nondet_int()
    __ESBMC_assume(n >= 0 and n <= 10)
    wcswidth_loop(pwcs, n)


main()
