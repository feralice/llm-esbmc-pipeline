def pivot_raises_on_missing_columns(columns_is_none: bool) -> bool:
    return False


def pivot_raises_on_missing_columns_fixed(columns_is_none: bool) -> bool:
    if columns_is_none:
        return True
    return False


def main() -> None:
    columns_is_none: bool = nondet_bool()
    buggy: bool = pivot_raises_on_missing_columns(columns_is_none)
    correct: bool = pivot_raises_on_missing_columns_fixed(columns_is_none)
    assert buggy == correct


main()
