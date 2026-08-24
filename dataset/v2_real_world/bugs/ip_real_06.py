def buggy_elem(v: int, i: int) -> int:
    # Real code (pandas/core/reshape/reshape.py:_unstack_multiple, BugsInPy
    # pandas #38): `clocs = [v if i > v else v - 1 for v in clocs]` compares
    # each element against a stale loop variable `i` left over from an
    # earlier, unrelated `for i in range(len(clocs))` loop, instead of the
    # `val` just processed in the current iteration.
    if i > v:
        return v
    return v - 1


def correct_elem(v: int, val: int) -> int:
    # Fix: `clocs = [v if v < val else v - 1 for v in clocs]`.
    if v < val:
        return v
    return v - 1


def main() -> None:
    v: int = nondet_int()
    i: int = nondet_int()
    val: int = nondet_int()
    b: int = buggy_elem(v, i)
    c: int = correct_elem(v, val)
    assert b == c


main()
