def tqdm_len(total_not_yet_set: bool) -> None:
    # Real code (tqdm/_tqdm.py, tqdm.__len__, BugsInPy tqdm#6): pre-fix,
    # the fallback branch reads `self.total` directly when the wrapped
    # iterable has no shape/__len__; if __len__ is invoked before __init__
    # has assigned `self.total` at all (not merely set it to None), that's
    # an AttributeError, not a None-value read. The fix uses
    # `getattr(self, "total", None)`. ESBMC-Python's class model requires
    # declared instance attributes, so it doesn't naturally represent
    # "attribute not yet assigned" -- the crash is made explicit via assert
    # on the real precondition instead.
    assert not total_not_yet_set


def main() -> None:
    total_not_yet_set: bool = nondet_bool()
    tqdm_len(total_not_yet_set)


main()
