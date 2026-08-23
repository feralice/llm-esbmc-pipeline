def build_exc_info(is_correct_order: bool) -> bool:
    # Real code (scrapy/contracts/__init__.py:84-87, eb_wrapper): pre-fix
    # built `exc_info = failure.value, failure.type, failure.getTracebackObject()`
    # -- swapped element order versus Python's standard (type, value,
    # traceback) triple that unittest.TestResult.addError expects,
    # confusing consumers that assume exc_info[0] is an exception class.
    # Fixed to `failure.type, failure.value, failure.getTracebackObject()`.
    return is_correct_order


def main() -> None:
    is_correct_order: bool = nondet_bool()
    __ESBMC_assume(not is_correct_order)
    result: bool = build_exc_info(is_correct_order)
    assert result == True


main()
