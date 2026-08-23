def buggy_len(start_index: int, end_index: int, batch_size: int, stride: int) -> int:
    # Real code (keras/preprocessing/sequence.py:TimeseriesGenerator.__len__,
    # BugsInPy keras bug #28): `int(np.ceil((end_index - start_index) /
    # (batch_size * stride)))` treats the [start_index, end_index] range as
    # exclusive of end_index, undercounting by one step whenever the range is
    # meant to be inclusive (the fix also adds a start_index <= end_index
    # precondition check, modeled here as an assumption instead).
    diff: int = end_index - start_index
    denom: int = batch_size * stride
    return (diff + denom - 1) // denom


def correct_len(start_index: int, end_index: int, batch_size: int, stride: int) -> int:
    # Fix: end_index is inclusive, so the span is (end_index - start_index + 1).
    diff: int = end_index - start_index + 1
    denom: int = batch_size * stride
    return (diff + denom - 1) // denom


def main() -> None:
    start_index: int = nondet_int()
    end_index: int = nondet_int()
    batch_size: int = nondet_int()
    stride: int = nondet_int()
    __ESBMC_assume(start_index >= 0 and start_index < 1000)
    __ESBMC_assume(end_index >= start_index and end_index < 1000)
    __ESBMC_assume(batch_size >= 1 and batch_size <= 10)
    __ESBMC_assume(stride >= 1 and stride <= 10)

    buggy: int = buggy_len(start_index, end_index, batch_size, stride)
    correct: int = correct_len(start_index, end_index, batch_size, stride)
    assert buggy == correct


main()
