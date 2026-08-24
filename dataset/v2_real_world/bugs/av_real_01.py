def cli_bool_option_value(key_present: bool, value: bool) -> bool:
    # Real code (youtube_dl/utils.py:cli_bool_option): param = params.get(param);
    # assert isinstance(param, bool). dict.get() returns None when the key is
    # absent -- a routine, expected case ("this option wasn't passed") -- but
    # the assert doesn't guard against it, so a missing key crashes instead
    # of degrading gracefully.
    if key_present:
        param = value
    else:
        param = None
    assert isinstance(param, bool)
    return param


def main() -> None:
    key_present: bool = nondet_bool()
    value: bool = nondet_bool()
    cli_bool_option_value(key_present, value)


main()
