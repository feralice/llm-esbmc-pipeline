# Regra none_guards_ordering. Gêmeo seguro de none_ordem_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def f(limit: Optional[int], n: int) -> bool:
    return n >= limit


def main() -> None:
    limit: Optional[int] = None
    if nondet_bool():
        limit = 5
    __ESBMC_assume(limit is not None)
    r: bool = f(limit, 3)
    assert r or not r


main()
