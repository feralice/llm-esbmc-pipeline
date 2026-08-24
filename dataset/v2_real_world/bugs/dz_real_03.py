def hash_expand_range(crc: int, idx: int, range_begin: int, range_end: int) -> int:
    # Real code (croniter/croniter.py:HashExpander, pre-fix): a hashed cron
    # field like "H/0" or a malformed range like "* * R/0 * *" can make
    # range_end == range_begin - 1, so range_end - range_begin + 1 == 0.
    # Nothing before this line rejects that -- real ZeroDivisionError on
    # `(crc >> idx) % (range_end - range_begin + 1)`.
    rng: int = range_end - range_begin + 1
    assert rng != 0
    return ((crc >> idx) % rng) + range_begin


def main() -> None:
    crc: int = nondet_int()
    idx: int = nondet_int()
    range_begin: int = nondet_int()
    range_end: int = nondet_int()
    __ESBMC_assume(crc >= 0)
    __ESBMC_assume(idx >= 0)
    __ESBMC_assume(idx < 32)
    hash_expand_range(crc, idx, range_begin, range_end)


main()
