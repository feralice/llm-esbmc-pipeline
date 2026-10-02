SELF_ID: int = 1
OTHER_ID: int = 2


def buggy_should_raise(cached_is_none: bool, cached_id: int) -> bool:
    # Real code (tornado/httpclient.py:AsyncHTTPClient.close, BugsInPy tornado
    # bug #3): `if self._instance_cache.get(self.io_loop) is not self: raise
    # RuntimeError(...)`. dict.get() returns None when the weakref-keyed entry
    # was already cleared (observed from __del__); `None is not self` is True,
    # so a legitimate cleared-cache close spuriously raised.
    if cached_is_none:
        return True
    return cached_id != SELF_ID


def correct_should_raise(cached_is_none: bool, cached_id: int) -> bool:
    # Fix: pop with a None default, and only raise when the popped value is
    # neither None nor self.
    if cached_is_none:
        return False
    return cached_id != SELF_ID


def main() -> None:
    cached_is_none: bool = nondet_bool()
    cached_id: int = nondet_int()
    __ESBMC_assume(cached_id == SELF_ID or cached_id == OTHER_ID)

    buggy: bool = buggy_should_raise(cached_is_none, cached_id)
    correct: bool = correct_should_raise(cached_is_none, cached_id)
    assert buggy == correct


main()
