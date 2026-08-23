def url_concat(args_is_none: bool) -> None:
    # Real code (tornado/httputil.py, url_concat, BugsInPy tornado#9):
    # pre-fix, the function has no `if args is None: return url` early
    # return; it falls into `isinstance(args, dict)` (False for None) and
    # then the else branch, which assumes args is an iterable of (key,
    # value) pairs -- iterating None raises TypeError. The fix's entire
    # diff is that one guard line, so the real precondition is asserted
    # directly rather than reproducing urlparse/query-string internals
    # ESBMC-Python does not model.
    assert not args_is_none


def main() -> None:
    args_is_none: bool = nondet_bool()
    url_concat(args_is_none)


main()
