# Fix jmespath.py 8f14a303: return self.__class__(matches) unconditionally.
def multi_get(has_matches: bool) -> list:
    matches: list = [1] if has_matches else []
    return matches


def main() -> None:
    has_matches: bool = nondet_bool()
    __ESBMC_assume(not has_matches)
    result = multi_get(has_matches)
    assert result == []


main()
