# Regra none_guards_subscript. Gêmeo seguro de none_indice_campo: o mesmo programa com o ramo não None assumido.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.xs: Optional[list[int]] = None
        if nondet_bool():
            self.xs = [1]


def main() -> None:
    b = Box()
    __ESBMC_assume(b.xs is not None)
    y = b.xs[0]


main()
