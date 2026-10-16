# Regra none_guards_membership. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.s: Optional[str] = None
        if nondet_bool():
            self.s = "xy"


def main() -> None:
    b = Box()
    found = "ab" in b.s


main()
