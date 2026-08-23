def format_headers(headerrow_is_none: bool) -> None:
    # Real code (python-tabulate, simple_separated_format): built a
    # TableFormat with headerrow=None; printing headers with that format
    # crashes with TypeError instead of reusing the data row format.
    # Real GitHub issue #15.
    assert not headerrow_is_none


def main() -> None:
    headerrow_is_none: bool = nondet_bool()
    format_headers(headerrow_is_none)


main()
