# Fix youtube-dl 5b232f46: return [] when params.get(param) is None.
def cli_bool_option_value(key_present: bool, value: bool) -> bool:
    if key_present:
        param = value
    else:
        param = None
    if param is None:
        return False
    assert isinstance(param, bool)
    return param


def main() -> None:
    key_present: bool = nondet_bool()
    value: bool = nondet_bool()
    cli_bool_option_value(key_present, value)


main()
