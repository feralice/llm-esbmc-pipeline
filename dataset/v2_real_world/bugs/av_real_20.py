def advance_column_buggy(current_column: int, char: str) -> int:
    if char == ' ':
        return current_column + 1
    elif char == '\t':
        return current_column + 4
    return current_column


def advance_column_fixed(current_column: int, char: str) -> int:
    if char in ' \t':
        return current_column + 1
    return current_column


def main() -> None:
    current_column: int = 0
    char: str = '\t'
    buggy: int = advance_column_buggy(current_column, char)
    correct: int = advance_column_fixed(current_column, char)
    assert buggy == correct


main()
