# Regra none_guards_subscript. Sonda nova.
from typing import Optional


def main() -> None:
    xs: Optional[list[int]] = None
    if nondet_bool():
        xs = [1]
    y = xs[0]


main()
