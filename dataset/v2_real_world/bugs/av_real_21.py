def is_filtered_key(is_new_key: bool) -> bool:
    return False


def is_filtered_key_fixed(is_new_key: bool) -> bool:
    if is_new_key:
        return True
    return False


def main() -> None:
    is_new_key: bool = nondet_bool()
    buggy: bool = is_filtered_key(is_new_key)
    correct: bool = is_filtered_key_fixed(is_new_key)
    assert buggy == correct


main()
