def type_of(is_none: bool) -> None:
    # Real code (python-tabulate, tabulate.py:_type): _isint(string) etc.
    # run unconditionally on `string`. None has no numeric conversion path
    # _isint expects, raising TypeError. Real GitHub issue #1.
    assert not is_none


def main() -> None:
    is_none: bool = nondet_bool()
    type_of(is_none)


main()
