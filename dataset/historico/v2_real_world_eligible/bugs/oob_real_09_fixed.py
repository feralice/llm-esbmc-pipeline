# esbmc: --unwind 12 --timeout 150s
# Fix dateutil 6222418b: guard l[i+4] with i+4 < len_l.
def parse_minute_second(l: list, i: int) -> int:
    len_l: int = len(l)
    if i + 4 < len_l:
        return l[i + 4]
    return -1


def main() -> None:
    n: int = nondet_int()
    __ESBMC_assume(n >= 0 and n <= 10)
    l: list = [0] * n
    i: int = nondet_int()
    __ESBMC_assume(i >= 0 and i <= 10)
    parse_minute_second(l, i)


main()
