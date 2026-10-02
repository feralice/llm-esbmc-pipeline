def total_after_init(total_is_none: bool, iterable_is_none: bool, iterable_len: int, disable: bool) -> int:
    total: int = 0
    total_unset: bool = total_is_none
    if disable:
        # BUG (tqdm/_tqdm.py __init__, BugsInPy tqdm bug #5): the real code
        # computes `total = len(iterable)` (when total wasn't given explicitly)
        # AFTER this early-return branch for disable=True, so a disabled
        # progress bar with an iterable but no explicit total silently keeps
        # total unset here instead of picking up the iterable's length. The
        # fix moves that computation above the disable check.
        return -1 if total_unset else total
    if total_unset and not iterable_is_none:
        total = iterable_len
        total_unset = False
    return -1 if total_unset else total


def main() -> None:
    iterable_len: int = nondet_int()
    __ESBMC_assume(iterable_len > 0)
    # Real caller precondition: an iterable was passed (iterable_is_none=False)
    # and no explicit total was given (total_is_none=True); len() doesn't
    # depend on whether the bar is disabled, so total should still resolve to
    # the iterable's length.
    result: int = total_after_init(True, False, iterable_len, True)
    assert result == iterable_len


main()
