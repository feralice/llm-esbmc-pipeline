def check_decimal_suffix(decimal_is_none: bool) -> None:
    # Real code (inflect.py, engine.number_to_words): num.endswith(decimal)
    # runs unconditionally; decimal=None disables decimal-word substitution
    # by caller convention, but str.endswith(None) raises TypeError.
    assert not decimal_is_none


def main() -> None:
    decimal_is_none: bool = nondet_bool()
    check_decimal_suffix(decimal_is_none)


main()
