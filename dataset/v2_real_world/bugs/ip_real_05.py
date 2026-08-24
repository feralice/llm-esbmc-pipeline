def buggy_gt(a: int, b: int) -> bool:
    # Real code (lib/ansible/utils/version.py:_Alpha.__gt__ /
    # _Numeric.__gt__, BugsInPy ansible #2): `__gt__` was defined as
    # `not self.__lt__(other)`, i.e. "not less than" -- which is also true
    # when the two values are equal, so `a > a` incorrectly evaluates True.
    return a >= b


def correct_gt(a: int, b: int) -> bool:
    return a > b


def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    r1: bool = buggy_gt(a, b)
    r2: bool = correct_gt(a, b)
    assert r1 == r2


main()
