def buggy_should_raise(has_colon: bool, has_dslash: bool, starts_data: bool) -> bool:
    # Real code (scrapy/http/request/__init__.py:_set_url, BugsInPy scrapy #37):
    # `if ':' not in self._url: raise ValueError('Missing scheme...')`. Only
    # flags a URL as scheme-less when it has NO colon at all, so a Windows
    # path like "C:\Users\x" (has a colon, no real scheme) slips through
    # unflagged.
    return not has_colon


def correct_should_raise(has_dslash: bool, starts_data: bool) -> bool:
    # Fixed condition: `('://' not in url) and (not url.startswith('data:'))`.
    return (not has_dslash) and (not starts_data)


def main() -> None:
    has_colon: bool = nondet_bool()
    has_dslash: bool = nondet_bool()
    starts_data: bool = nondet_bool()
    __ESBMC_assume(has_dslash <= has_colon)
    b: bool = buggy_should_raise(has_colon, has_dslash, starts_data)
    c: bool = correct_should_raise(has_dslash, starts_data)
    assert b == c


main()
