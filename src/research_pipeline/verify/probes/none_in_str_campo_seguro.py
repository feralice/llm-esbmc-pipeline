# Regra none_guards_membership. Gêmeo seguro de none_in_str_campo: o mesmo programa com o ramo não None assumido.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.s: Optional[str] = None
        if nondet_bool():
            self.s = "xy"


def main() -> None:
    b = Box()
    __ESBMC_assume(b.s is not None)
    found = "ab" in b.s


main()
