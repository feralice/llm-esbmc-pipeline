def tokenize_zwj_branch(result: list, string: str, i: int) -> int:
    last: int = result[-1]
    prev_char_ord: int = ord(string[i - 1])
    return last + prev_char_ord


def main() -> None:
    result: list = []
    string: str = "a"
    i: int = 0
    tokenize_zwj_branch(result, string, i)


main()
