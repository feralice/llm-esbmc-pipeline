# Regra none_guards_membership. Gêmeo seguro de none_in_lista_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def main() -> None:
    xs: Optional[list[str]] = None
    if nondet_bool():
        xs = ["a"]
    __ESBMC_assume(xs is not None)
    found = "a" in xs


main()
