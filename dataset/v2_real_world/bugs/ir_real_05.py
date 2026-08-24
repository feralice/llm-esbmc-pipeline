def string_to_int_buggy(alphabet_len: int, alphabet_index_len: int, d0: int, d1: int) -> int:
    # Real code (shortuuid/main.py:string_to_int, pre-fix, issue #115):
    # when alphabet_index is passed explicitly, the docstring says `alphabet`
    # is ignored, but `alpha_len = len(alphabet)` still used the (ignored)
    # alphabet's length as the radix instead of len(alphabet_index), decoding
    # in the wrong base whenever the two lengths differ.
    alpha_len: int = alphabet_len
    number: int = 0
    number = number * alpha_len + d0
    number = number * alpha_len + d1
    return number


def string_to_int_fixed(alphabet_len: int, alphabet_index_len: int, d0: int, d1: int) -> int:
    alpha_len: int = alphabet_index_len
    number: int = 0
    number = number * alpha_len + d0
    number = number * alpha_len + d1
    return number


def main() -> None:
    alphabet_len: int = nondet_int()
    alphabet_index_len: int = nondet_int()
    d0: int = nondet_int()
    d1: int = nondet_int()
    __ESBMC_assume(alphabet_len >= 2 and alphabet_len <= 10)
    __ESBMC_assume(alphabet_index_len >= 2 and alphabet_index_len <= 10)
    __ESBMC_assume(alphabet_len != alphabet_index_len)
    __ESBMC_assume(d0 >= 0 and d0 < alphabet_index_len)
    __ESBMC_assume(d1 >= 0 and d1 < alphabet_index_len)
    assert string_to_int_buggy(alphabet_len, alphabet_index_len, d0, d1) == \
        string_to_int_fixed(alphabet_len, alphabet_index_len, d0, d1)


main()
