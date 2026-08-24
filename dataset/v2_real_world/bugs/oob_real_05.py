def buggy_check(src_txt: str) -> bool:
    # Real code (black.py, lib2to3_parse, BugsInPy black bug #17):
    # src_txt[-1] on an empty string raises IndexError; the fix uses the
    # slice src_txt[-1:] which is safe on an empty string.
    return src_txt[-1] != "\n"


def main() -> None:
    src_txt: str = ""
    buggy_check(src_txt)


main()
