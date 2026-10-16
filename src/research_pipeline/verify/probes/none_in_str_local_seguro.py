# Regra none_guards_membership. Gêmeo seguro de none_in_str_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def main() -> None:
    s: Optional[str] = None
    if nondet_bool():
        s = "xy"
    __ESBMC_assume(s is not None)
    found = "ab" in s


main()
