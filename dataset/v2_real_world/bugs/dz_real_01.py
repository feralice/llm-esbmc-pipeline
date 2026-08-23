def color_interp_distance(xind_i: float, x_ind: float, x_ind_prev: float) -> float:
    # Real caller precondition (matplotlib/colors.py:makeMappingArray): only
    # DECREASING x is rejected before this call ("data mapping points must be
    # in increasing order"); EQUAL adjacent x values are allowed through.
    __ESBMC_assume(x_ind >= x_ind_prev)

    # ESBMC-Python's `/` always lowers to ieee_div (even for int operands) and
    # is NOT covered by the default division-by-zero check (that check only
    # fires on integer ID_div, e.g. Python's `//`). Real Python raises
    # ZeroDivisionError on x/0.0 regardless of type. This assert makes that
    # real-world failure mode explicit and checkable by ESBMC.
    assert x_ind != x_ind_prev
    distance = (xind_i - x_ind_prev) / (x_ind - x_ind_prev)
    return distance


def main() -> None:
    xind_i: float = nondet_float()
    x_ind: float = nondet_float()
    x_ind_prev: float = nondet_float()
    __ESBMC_assume(xind_i == xind_i and x_ind == x_ind and x_ind_prev == x_ind_prev)
    color_interp_distance(xind_i, x_ind, x_ind_prev)


main()
