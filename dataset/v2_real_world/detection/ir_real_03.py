def try_match_char_class_range(pattern: str, pattern_len: int, string: str) -> int:
    """Match [x-y]+ or [x-y]* patterns"""
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
