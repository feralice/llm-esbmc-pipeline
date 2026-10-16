# Regra none_guards_subscript. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.xs: Optional[list[int]] = None
        if nondet_bool():
            self.xs = [1]


def main() -> None:
    b = Box()
    y = b.xs[0]


main()
