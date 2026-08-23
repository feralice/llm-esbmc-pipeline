def ensure_trailing_newline(src_txt: str) -> str:
    # Real code (black.py:lib2to3_parse, BugsInPy black bug #17):
    # `src_txt[-1] != "\n"` raises IndexError on an empty string (e.g. an
    # empty source file after decode_bytes()); the fix uses the slice form
    # `src_txt[-1:]` instead, which returns "" (falsy-safe) rather than
    # indexing out of bounds.
    if src_txt[-1] != "\n":
        src_txt += "\n"
    return src_txt


def main() -> None:
    src_txt: str = ""
    ensure_trailing_newline(src_txt)


main()
