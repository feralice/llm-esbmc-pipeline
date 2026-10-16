# Regra none_guards_call. Sonda nova.
from typing import Optional


def main() -> None:
    v: Optional[str] = None
    if nondet_bool():
        v = "1.5"
    f = float(v)


main()
