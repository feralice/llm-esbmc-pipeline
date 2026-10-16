# Regra none_guards_ordering. Gêmeo seguro de none_ordem_campo: o mesmo programa com o ramo não None assumido.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.limit: Optional[int] = None
        if nondet_bool():
            self.limit = 5


def main() -> None:
    b = Box()
    __ESBMC_assume(b.limit is not None)
    r: bool = 3 >= b.limit


main()
