PERIOD_INDEX = 1


def to_timestamp_guard(index_type_tag: int) -> None:
    # Real code (pandas/core/series.py:Series.to_timestamp):
    # `assert isinstance(self.index, PeriodIndex)`. Series.index can
    # legitimately be any index type (RangeIndex, DatetimeIndex, a custom
    # one, ...) set by the caller -- the assert crashes with an opaque
    # AssertionError for any caller whose index isn't a PeriodIndex, instead
    # of a proper, catchable error (the real fix replaces it with
    # `raise TypeError(...)`).
    assert index_type_tag == PERIOD_INDEX


def main() -> None:
    index_type_tag: int = nondet_int()
    to_timestamp_guard(index_type_tag)


main()
