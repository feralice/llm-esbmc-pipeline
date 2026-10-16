# Regra none_guards_membership. Origem: docs/projeto/possiveis_problemas/26_in_str_none.py.
from typing import Optional


def main() -> None:
    s: Optional[str] = None
    if nondet_bool():
        s = "xy"
    found = "ab" in s


main()
