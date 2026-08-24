def interpolate_step_ratio(h_src: int, chunk_size: int) -> float:
    # Real caller precondition (aws-neuron/nki-samples issue #125, fixed by
    # PR #126): before the fix, callers only guaranteed h_src > 0 and
    # chunk_size > 0 (default chunk_size=10). No lower bound of 2 was
    # enforced on chunk_size, so chunk_size == 1 collapses step_size to 0.
    __ESBMC_assume(h_src > 0)
    __ESBMC_assume(chunk_size > 0)

    wdw_size = chunk_size
    step_size = wdw_size - 1

    # ESBMC-Python's `/` always lowers to ieee_div and is NOT covered by the
    # default division-by-zero check (see dz_real_01 for the same gotcha).
    assert step_size != 0
    return (h_src - wdw_size) / step_size


def main() -> None:
    h_src: int = nondet_int()
    chunk_size: int = nondet_int()
    interpolate_step_ratio(h_src, chunk_size)


main()
