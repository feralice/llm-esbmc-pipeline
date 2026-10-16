# Regra none_guards_arithmetic. Origem: docs/projeto/possiveis_problemas/10_optional_soma_falso_negativo.py.
from typing import Optional


def inc(v: Optional[int]) -> int:
    return v + 1


def main() -> None:
    v: Optional[int] = None
    if nondet_bool():
        v = nondet_int()
    inc(v)


main()
