# Regra none_guards_call. Gêmeo seguro de none_int_campo: o mesmo programa com o ramo não None assumido.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.status: Optional[str] = None
        if nondet_bool():
            self.status = "7"


def main() -> None:
    b = Box()
    __ESBMC_assume(b.status is not None)
    code = int(b.status)


main()
