# Regra none_guards_attribute. Gêmeo seguro de none_atributo_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


class Ex:
    def shutdown(self) -> None:
        pass


def main() -> None:
    e: Optional[Ex] = None
    if nondet_bool():
        e = Ex()
    __ESBMC_assume(e is not None)
    e.shutdown()


main()
