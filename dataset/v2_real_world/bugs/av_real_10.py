def buggy_column(current_column: int, is_tab: bool) -> int:
    # Real code (blib2to3/pgen2/driver.py, BugsInPy black bug #10): a tab
    # character advances the column counter by 1, same as a space, instead
    # of by 4, miscounting indentation width.
    return current_column + 1


def correct_column(current_column: int, is_tab: bool) -> int:
    if is_tab:
        return current_column + 4
    return current_column + 1


def main() -> None:
    current_column: int = nondet_int()
    is_tab: bool = nondet_bool()
    __ESBMC_assume(current_column >= 0 and is_tab)
    assert buggy_column(current_column, is_tab) == correct_column(current_column, is_tab)


main()
