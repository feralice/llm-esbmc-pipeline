def send2trash_buggy(paths_empty: bool) -> int:
    if paths_empty:
        return 1
    return 0


def send2trash_correct(paths_empty: bool) -> int:
    if paths_empty:
        return 0
    return 0


def main() -> None:
    paths_empty: bool = nondet_bool()
    buggy: int = send2trash_buggy(paths_empty)
    correct: int = send2trash_correct(paths_empty)
    assert buggy == correct


main()
