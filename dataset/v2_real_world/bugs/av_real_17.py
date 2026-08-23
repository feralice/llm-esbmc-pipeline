def unified_strdate_buggy(found: bool) -> bool:
    return True


def unified_strdate_fixed(found: bool) -> bool:
    return found


def main() -> None:
    found: bool = False
    buggy: bool = unified_strdate_buggy(found)
    correct: bool = unified_strdate_fixed(found)
    assert buggy == correct


main()
