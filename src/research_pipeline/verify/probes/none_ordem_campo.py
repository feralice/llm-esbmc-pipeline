# Regra none_guards_ordering. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.limit: Optional[int] = None
        if nondet_bool():
            self.limit = 5


def main() -> None:
    b = Box()
    r: bool = 3 >= b.limit


main()
