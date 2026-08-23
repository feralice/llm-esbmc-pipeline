def should_raise_buggy(current_is_none: bool) -> bool:
    return current_is_none


def should_raise_fixed(current_is_none: bool) -> bool:
    return not current_is_none


def main() -> None:
    current_is_none: bool = True
    buggy: bool = should_raise_buggy(current_is_none)
    correct: bool = should_raise_fixed(current_is_none)
    assert buggy == correct


main()
