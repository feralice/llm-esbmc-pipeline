def numpy_int8_abs(value: int) -> int:
    """Model abs() on a signed NumPy int8, including two's-complement wrap."""
    assert -128 <= value <= 127
    if value == -128:
        return -128
    if value < 0:
        return -value
    return value


def nonsingular_magnitude(vmin: int, vmax: int) -> int:
    """Pre-fix scalar core of matplotlib.transforms.nonsingular()."""
    left: int = numpy_int8_abs(vmin)
    right: int = numpy_int8_abs(vmax)
    magnitude: int = max(left, right)
    assert magnitude >= 0
    return magnitude


def verify_nonsingular_magnitude() -> None:
    vmin: int = nondet_int()
    vmax: int = nondet_int()
    __ESBMC_assume(-128 <= vmin and vmin <= 127)
    __ESBMC_assume(-128 <= vmax and vmax <= 127)
    nonsingular_magnitude(vmin, vmax)


verify_nonsingular_magnitude()
