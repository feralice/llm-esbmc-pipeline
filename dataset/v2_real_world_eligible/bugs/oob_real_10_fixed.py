# esbmc: --unwind 5 --timeout 250s
# Fix python-tabulate 20c6370d: guard list_of_lists[0] when data is empty.
def compute_num_cols(list_of_lists: list[list[int]]) -> int:
    if not list_of_lists:
        return 0
    return len(list_of_lists[0])


def main() -> None:
    n: int = nondet_int()
    __ESBMC_assume(n >= 0 and n <= 3)
    list_of_lists: list[list[int]] = []
    i: int = 0
    while i < n:
        list_of_lists.append([1, 2])
        i += 1
    compute_num_cols(list_of_lists)


main()
