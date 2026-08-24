def compute_num_cols(list_of_lists: list) -> int:
    return len(list_of_lists[0])


def main() -> None:
    n: int = nondet_int()
    __ESBMC_assume(n >= 0 and n <= 3)
    list_of_lists: list = []
    i: int = 0
    while i < n:
        list_of_lists.append([1, 2])
        i += 1
    compute_num_cols(list_of_lists)


main()
