def is_file_check(v_is_none: bool) -> None:
    # Real code (voluptuous/validators.py, IsFile/IsDir/PathExists):
    # os.path.isfile(v) etc. run unconditionally on v; real os.path
    # functions raise TypeError on None. Fixes #204.
    assert not v_is_none


def main() -> None:
    v_is_none: bool = nondet_bool()
    is_file_check(v_is_none)


main()
