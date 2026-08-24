def compute_limit_high_buggy(vmin: float, vmax: float, oldmin: float, oldmax: float) -> float:
    return max(vmin, vmax, oldmax)


def compute_limit_high_correct(vmin: float, vmax: float, oldmin: float, oldmax: float) -> float:
    return max(vmin, vmax, oldmin)


def main() -> None:
    vmin: float = nondet_float()
    vmax: float = nondet_float()
    oldmin: float = nondet_float()
    oldmax: float = nondet_float()
    __ESBMC_assume(vmin == vmin and vmax == vmax and oldmin == oldmin and oldmax == oldmax)
    buggy: float = compute_limit_high_buggy(vmin, vmax, oldmin, oldmax)
    correct: float = compute_limit_high_correct(vmin, vmax, oldmin, oldmax)
    assert buggy == correct


main()
