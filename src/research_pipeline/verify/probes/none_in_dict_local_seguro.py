# Regra none_guards_membership. Gêmeo seguro de none_in_dict_local: o mesmo programa com o ramo não None assumido.
from typing import Optional


def f(classes: Optional[dict], tag: str) -> bool:
    return tag in classes


def main() -> None:
    classes: Optional[dict] = None
    if nondet_bool():
        classes = {"pre": "x"}
    __ESBMC_assume(classes is not None)
    f(classes, "pre")


main()
