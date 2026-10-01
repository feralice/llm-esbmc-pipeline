# Fix emoji 14a3a162: guard with `result and ... i > 0` before result[-1] / string[i - 1].
def tokenize_zwj_branch(result: list, string: str, i: int) -> int:
    if result and i > 0:
        last: int = result[-1]
        prev_char_ord: int = ord(string[i - 1])
        return last + prev_char_ord
    return 0


def main() -> None:
    result: list = []
    string: str = "a"
    i: int = 0
    tokenize_zwj_branch(result, string, i)


main()
