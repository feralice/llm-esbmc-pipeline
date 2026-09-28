def rating_ratio(not_parsed: int, num_substrings: int) -> float:
    # Real code (dateparser/search/search.py:ExactLanguageSearch.choose_best_split,
    # pre-fix): num_substrings = len(possible_substrings_splits[i]) can
    # legitimately be 0 (an empty split option), and nothing upstream guards
    # against it before float(not_parsed)/float(num_substrings) -- real
    # ZeroDivisionError (checked natively by ESBMC-Python 8.5.0).
    return float(not_parsed) / float(num_substrings)


def main() -> None:
    not_parsed: int = nondet_int()
    num_substrings: int = nondet_int()
    __ESBMC_assume(not_parsed >= 0)
    __ESBMC_assume(num_substrings >= 0)
    __ESBMC_assume(not_parsed <= num_substrings)
    rating_ratio(not_parsed, num_substrings)


main()
