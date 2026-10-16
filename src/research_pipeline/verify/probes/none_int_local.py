# Regra none_guards_call. Origem: docs/projeto/possiveis_problemas/39_int_de_none.py.
from typing import Optional


def main() -> None:
    status: Optional[str] = None
    if nondet_bool():
        status = "7"
    code = int(status)


main()
