# Regra none_guards_membership. Origem: docs/projeto/possiveis_problemas/04_inNone.py.
from typing import Optional


def f(classes: Optional[dict], tag: str) -> bool:
    return tag in classes


def main() -> None:
    classes: Optional[dict] = None
    if nondet_bool():
        classes = {"pre": "x"}
    f(classes, "pre")


main()
