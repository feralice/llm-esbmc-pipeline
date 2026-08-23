def buggy_init_raises(response_is_none: bool, text_is_none: bool) -> bool:
    # Real code (scrapy/selector/unified.py:Selector.__init__, BugsInPy
    # scrapy #12): before the fix, __init__ never checked that `response`
    # and `text` are mutually exclusive, so passing both silently picks one
    # instead of raising.
    return False


def correct_init_raises(response_is_none: bool, text_is_none: bool) -> bool:
    # Fix adds: `if not(response is None or text is None): raise ValueError(...)`.
    return not (response_is_none or text_is_none)


def main() -> None:
    response_is_none: bool = nondet_bool()
    text_is_none: bool = nondet_bool()
    b: bool = buggy_init_raises(response_is_none, text_is_none)
    c: bool = correct_init_raises(response_is_none, text_is_none)
    assert b == c


main()
