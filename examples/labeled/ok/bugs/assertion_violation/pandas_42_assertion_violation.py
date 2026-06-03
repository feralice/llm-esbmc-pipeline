# Extracted from pandas/core/dtypes/common.py — pandas data analysis library
# Source: BugsInPy pandas #42
# Bug: assert fires when only one side is IntervalDtype (e.g. left is Interval, right is not)
# Real fix: comparison logic rewritten to handle mixed dtype cases
def compare_interval_dtype(left_is_interval: bool, right_is_interval: bool) -> bool:
    if left_is_interval or right_is_interval:
        assert left_is_interval and right_is_interval
        return True

    return False