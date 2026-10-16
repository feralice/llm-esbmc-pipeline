# Regra none_guards_arithmetic. Gêmeo seguro de none_soma_campo: o mesmo programa com o ramo não None assumido.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.v: Optional[int] = None
        if nondet_bool():
            self.v = 3


def main() -> None:
    b = Box()
    __ESBMC_assume(b.v is not None)
    x = b.v + 1


main()
