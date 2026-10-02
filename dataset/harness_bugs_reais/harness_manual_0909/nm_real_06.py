def create_instance(constructor_returns_none: bool) -> bool:
    # Real code (scrapy/utils/misc.py, create_instance, BugsInPy scrapy#36):
    # pre-fix, `create_instance()` returns whatever `objcls.from_crawler(...)`
    # / `from_settings(...)` / `objcls(...)` produced, with no check that the
    # result isn't None -- a misbehaving extension can legitimately return
    # None, and the caller silently receives it. The fix raises TypeError
    # when the constructed instance is None. Modeled as an assert on the
    # postcondition the fix establishes.
    assert not constructor_returns_none
    return True


def main() -> None:
    constructor_returns_none: bool = nondet_bool()
    create_instance(constructor_returns_none)


main()
