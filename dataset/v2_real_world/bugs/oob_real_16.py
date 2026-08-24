def get_real_index_buggy(index: int, length: int) -> int:
    normalized: int = index + length if index < 0 else index
    real: int = normalized + length if normalized < 0 else normalized
    return real


def get_real_index_correct(index: int, length: int) -> int:
    real: int = index + length if index < 0 else index
    return real


def main() -> None:
    index: int = nondet_int()
    length: int = nondet_int()
    __ESBMC_assume(length >= 1 and length <= 20)
    __ESBMC_assume(index >= -2 * length and index < length)
    buggy: int = get_real_index_buggy(index, length)
    correct: int = get_real_index_correct(index, length)
    assert buggy == correct


main()
