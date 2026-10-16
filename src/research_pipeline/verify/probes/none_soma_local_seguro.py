# Regra none_guards_arithmetic. Gêmeo seguro de none_soma_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def inc(v: Optional[int]) -> int:
    return v + 1


def main() -> None:
    v: Optional[int] = None
    if nondet_bool():
        v = nondet_int()
    __ESBMC_assume(v is not None)
    inc(v)


main()
