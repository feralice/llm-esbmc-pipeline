# Regra none_guards_call. Sonda nova.
from typing import Optional


def main() -> None:
    xs: Optional[list[int]] = None
    if nondet_bool():
        xs = [1]
    n = len(xs)


main()
