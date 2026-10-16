# Regra none_guards_call. Gêmeo seguro de none_int_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def main() -> None:
    status: Optional[str] = None
    if nondet_bool():
        status = "7"
    __ESBMC_assume(status is not None)
    code = int(status)


main()
