def buggy_column(current_column: int, is_tab: bool) -> int:
    # Real code (blib2to3/pgen2/driver.py, BugsInPy black bug #10, pre-fix
    # commit f6643c4): a tab character advances the column counter by 4,
    # differently from a space (+1), miscounting indentation width relative
    # to what the parser expects downstream.
    if is_tab:
        return current_column + 4
    return current_column + 1


def correct_column(current_column: int, is_tab: bool) -> int:
    # Fix (commit 66aa676): unify tab and space, both advance by 1.
    return current_column + 1


def main() -> None:
    current_column: int = nondet_int()
    is_tab: bool = nondet_bool()
    __ESBMC_assume(current_column >= 0 and is_tab)
    assert buggy_column(current_column, is_tab) == correct_column(current_column, is_tab)


main()
