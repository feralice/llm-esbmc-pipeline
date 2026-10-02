def try_match_char_class_range_buggy(pattern: str, pattern_len: int, string: str) -> int:
    # Real code (ESBMC src/python-frontend/models/re.py, pre-#d8ad5349c1):
    # pattern_len != 7 is an off-by-one -- a real "[x-y]+"/"[x-y]*" pattern
    # is 6 characters long, so this recognizer never fires and always
    # returns -1 (falls through to a nondet/mismatch result) instead of
    # actually matching. string_len also drops the last real character
    # (len(string) - 1 instead of len(string)).
    if pattern_len != 7:
        return -1

    if not (pattern[0] == '[' and pattern[2] == '-' and pattern[4] == ']'):
        return -1

    quantifier: str = pattern[5]
    if quantifier != '+' and quantifier != '*':
        return -1

    start_char: str = pattern[1]
    end_char: str = pattern[3]
    string_len: int = len(string) - 1

    if string_len == 0:
        return 1 if quantifier == '*' else 0

    i: int = 0
    while i < string_len:
        c: str = string[i]
        if c < start_char or c > end_char:
            return 0
        i = i + 1
    return 1


def main() -> None:
    # "[a-z]+" is 6 characters and "abc" is entirely lowercase: a correct
    # matcher returns 1 (match). The buggy pattern_len check rejects every
    # 6-character pattern outright.
    pattern: str = "[a-z]+"
    r: int = try_match_char_class_range_buggy(pattern, 6, "abc")
    assert r == 1


main()
