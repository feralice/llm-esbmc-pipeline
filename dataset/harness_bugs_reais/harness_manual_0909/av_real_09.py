def buggy_bounds(vmin: float, vmax: float, oldmin: float, oldmax: float) -> float:
    # Real code (lib/matplotlib/axis.py, _make_getset_interval,
    # BugsInPy matplotlib bug #24): the else-branch swaps which extra bound
    # feeds max() vs min() -- oldmax feeds max() here, but should feed min().
    return max(max(vmin, vmax), oldmax)


def correct_bounds(vmin: float, vmax: float, oldmin: float, oldmax: float) -> float:
    return max(max(vmin, vmax), oldmin)


def main() -> None:
    vmin: float = nondet_float()
    vmax: float = nondet_float()
    oldmin: float = nondet_float()
    oldmax: float = nondet_float()
    __ESBMC_assume(vmin == vmin and vmax == vmax and oldmin == oldmin and oldmax == oldmax)
    assert buggy_bounds(vmin, vmax, oldmin, oldmax) == correct_bounds(vmin, vmax, oldmin, oldmax)


main()
