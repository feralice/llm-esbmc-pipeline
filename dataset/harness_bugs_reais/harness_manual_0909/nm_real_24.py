def reformat_many_finally(executor_is_none: bool) -> None:
    # Real code (black.py:reformat_many, BugsInPy black bug #1): ProcessPoolExecutor(...)
    # can raise OSError on platforms without multiprocessing support (e.g. AWS Lambda);
    # the fix catches that and falls back to executor=None, but the `finally` block still
    # called `executor.shutdown()` unconditionally, crashing with AttributeError on the
    # very platform the fallback was meant to support.
    assert not executor_is_none


def main() -> None:
    executor_is_none: bool = nondet_bool()
    reformat_many_finally(executor_is_none)


main()
