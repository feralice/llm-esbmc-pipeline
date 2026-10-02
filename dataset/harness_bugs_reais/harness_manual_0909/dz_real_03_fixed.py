# Fix croniter 7d319c51: raise CroniterBadCronError("Bad range") when rng == 0.
class CroniterBadCronError(Exception):
    pass


def hash_expand_range(crc: int, idx: int, range_begin: int, range_end: int) -> int:
    rng: int = range_end - range_begin + 1
    if rng == 0:
        raise CroniterBadCronError("Bad range")
    return ((crc >> idx) % rng) + range_begin


def main() -> None:
    crc: int = nondet_int()
    idx: int = nondet_int()
    range_begin: int = nondet_int()
    range_end: int = nondet_int()
    __ESBMC_assume(crc >= 0)
    __ESBMC_assume(idx >= 0)
    __ESBMC_assume(idx < 32)
    try:
        hash_expand_range(crc, idx, range_begin, range_end)
    except CroniterBadCronError:
        pass


main()
