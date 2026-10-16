# Regra none_guards_arithmetic. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.v: Optional[int] = None
        if nondet_bool():
            self.v = 3


def main() -> None:
    b = Box()
    x = b.v + 1


main()
