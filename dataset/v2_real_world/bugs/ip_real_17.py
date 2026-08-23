def status_message_is_known(status_in_table: bool) -> bool:
    return status_in_table


def status_message_is_known_fixed(status_in_table: bool) -> bool:
    return True


def main() -> None:
    status_in_table: bool = nondet_bool()
    buggy: bool = status_message_is_known(status_in_table)
    correct: bool = status_message_is_known_fixed(status_in_table)
    assert buggy == correct


main()
