# Regra none_guards_call. Gêmeo seguro de none_len_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def main() -> None:
    xs: Optional[list[int]] = None
    if nondet_bool():
        xs = [1]
    __ESBMC_assume(xs is not None)
    n = len(xs)


main()
