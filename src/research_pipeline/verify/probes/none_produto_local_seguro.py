# Regra none_guards_arithmetic. Gêmeo seguro de none_produto_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def f(t: Optional[int], s: int) -> int:
    return t * s


def main() -> None:
    t: Optional[int] = None
    if nondet_bool():
        t = 5
    __ESBMC_assume(t is not None)
    r: int = f(t, 2)
    assert r != -7777


main()
