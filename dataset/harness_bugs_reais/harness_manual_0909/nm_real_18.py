def format_seconds(seconds_is_none: bool) -> None:
    # Real code (tenacity/after.py, after_log): '%s' % retry_state.seconds_since_start
    # runs unconditionally; seconds_since_start is None when outcome_timestamp
    # is unset. Real GitHub issue #591, has a regression test.
    assert not seconds_is_none


def main() -> None:
    seconds_is_none: bool = nondet_bool()
    format_seconds(seconds_is_none)


main()
