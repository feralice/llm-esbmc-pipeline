from typing import Optional


def inc(v: Optional[int]) -> int:
    return v + 1


def main() -> None:
    v: Optional[int] = None
    if nondet_bool():
        v = nondet_int()
    inc(v)


main()
