def is_necessary_buggy(status_is_unknown: bool, status_is_done_or_disabled: bool, disable_time_set: bool) -> bool:
    return (not status_is_done_or_disabled) or disable_time_set


def is_necessary_fixed(status_is_unknown: bool, status_is_done_or_disabled: bool, disable_time_set: bool) -> bool:
    status_is_done_disabled_or_unknown: bool = status_is_done_or_disabled or status_is_unknown
    return (not status_is_done_disabled_or_unknown) or disable_time_set


def main() -> None:
    status_is_unknown: bool = True
    status_is_done_or_disabled: bool = False
    disable_time_set: bool = False
    buggy: bool = is_necessary_buggy(status_is_unknown, status_is_done_or_disabled, disable_time_set)
    correct: bool = is_necessary_fixed(status_is_unknown, status_is_done_or_disabled, disable_time_set)
    assert buggy == correct


main()
