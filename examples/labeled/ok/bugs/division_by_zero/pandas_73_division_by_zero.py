# Extracted from pandas/core/groupby/groupby.py — pandas data analysis library
# Source: BugsInPy pandas #73
# Bug: value / divisor raises ZeroDivisionError when divisor == 0 (e.g. empty group)
# Real fix: added zero-check before division in the groupby aggregation path
def pandas_division_behavior(value: float, divisor: float) -> float:
    return value / divisor