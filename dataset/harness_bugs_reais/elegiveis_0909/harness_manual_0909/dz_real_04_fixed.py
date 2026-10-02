# Fix aws-neuron/nki-samples PR #126: assert chunk_size >= 2 at kernel entry.
class KernelArgError(Exception):
    pass


def interpolate_step_ratio(h_src: int, chunk_size: int) -> float:
    __ESBMC_assume(h_src > 0)
    __ESBMC_assume(chunk_size > 0)
    if chunk_size < 2:
        raise KernelArgError("chunk_size must be >= 2")

    wdw_size = chunk_size
    step_size = wdw_size - 1

    return (h_src - wdw_size) / step_size


def main() -> None:
    h_src: int = nondet_int()
    chunk_size: int = nondet_int()
    try:
        interpolate_step_ratio(h_src, chunk_size)
    except KernelArgError:
        pass


main()
