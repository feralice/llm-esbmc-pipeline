def check_allowed_domain(domain_is_none: bool) -> None:
    # Real code (scrapy/spidermiddlewares/offsite.py,
    # OffsiteMiddleware.get_host_regex, BugsInPy scrapy#1): the pre-fix loop
    # calls `url_pattern.match(domain)` on every entry of `allowed_domains`
    # BEFORE the None-filter (`if d is not None`) that only applies later,
    # in a separate list comprehension building `domains`. A None entry in
    # allowed_domains therefore reaches `.match(None)` unguarded.
    # ESBMC-Python's re.match() type-validates its string argument and can
    # raise TypeError for it directly, but that check did not reliably
    # trigger once `domain` had passed through a function-parameter
    # boundary in this exact shape during testing -- the crash is made
    # explicit via assert on the real precondition instead, same pattern as
    # nm_real_01/02.
    assert not domain_is_none


def main() -> None:
    domain_is_none: bool = nondet_bool()
    check_allowed_domain(domain_is_none)


main()
