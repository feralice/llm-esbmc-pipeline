# Fix thefuck feb36ede: wrap the second pop in try/except IndexError (`git push -u`).
def remove_upstream_option(list_len: int, idx: int) -> None:
    parts: list = []
    for i in range(list_len):
        parts.append(i)
    parts.pop(idx)
    try:
        parts.pop(idx)
    except IndexError:
        pass


def main() -> None:
    list_len: int = nondet_int()
    idx: int = nondet_int()
    __ESBMC_assume(list_len >= 1 and list_len <= 4)
    __ESBMC_assume(idx >= 0 and idx < list_len)
    remove_upstream_option(list_len, idx)


main()
