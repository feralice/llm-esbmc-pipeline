def to_env_filtered(value_is_none: bool) -> None:
    # Real code (python-dotenv, src/dotenv/cli.py:run): dotenv_values(file)
    # can return None for a variable declared without a value (e.g. `FOO=`).
    # Before the fix, every value -- including None ones -- was passed
    # through to_env() unfiltered, crashing on a None value.
    assert not value_is_none


def main() -> None:
    value_is_none: bool = nondet_bool()
    to_env_filtered(value_is_none)


main()
