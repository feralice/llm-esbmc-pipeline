# esbmc: --unwind 6 --timeout 150s
# Fix dateparser 7098f635: 0 if not_parsed == 0 else not_parsed / num_substrings.
def rating_ratio(not_parsed: int, num_substrings: int) -> float:
    if not_parsed == 0:
        return 0.0
    return float(not_parsed) / float(num_substrings)


def main() -> None:
    not_parsed: int = nondet_int()
    num_substrings: int = nondet_int()
    __ESBMC_assume(not_parsed >= 0)
    __ESBMC_assume(num_substrings >= 0)
    __ESBMC_assume(not_parsed <= num_substrings)
    rating_ratio(not_parsed, num_substrings)


main()
