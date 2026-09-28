# Fix black 7fc6ce99: src_txt[-1:] instead of src_txt[-1].
def check(src_txt: str) -> bool:
    return src_txt[-1:] != "\n"


def main() -> None:
    src_txt: str = ""
    check(src_txt)


main()
