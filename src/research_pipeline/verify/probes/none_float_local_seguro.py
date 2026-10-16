# Regra none_guards_call. Gêmeo seguro de none_float_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def main() -> None:
    v: Optional[str] = None
    if nondet_bool():
        v = "1.5"
    __ESBMC_assume(v is not None)
    f = float(v)


main()
