def multi_get(has_matches: bool) -> list:
    # Real code (jmespath/ast.py, _Projection.multi_get): builds a `matches`
    # list, then only `return self.__class__(matches)` inside `if matches:`
    # -- no else branch, so an empty result falls through and implicitly
    # returns None instead of an empty list. Real GitHub issue #18.
    matches: list = [1] if has_matches else []
    if matches:
        return matches


def main() -> None:
    has_matches: bool = nondet_bool()
    __ESBMC_assume(not has_matches)
    result = multi_get(has_matches)
    assert result == []


main()
