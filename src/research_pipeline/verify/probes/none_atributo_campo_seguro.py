# Regra none_guards_attribute. Gêmeo seguro de none_atributo_campo: o mesmo programa com o ramo não None assumido.
from typing import Optional


class Node:
    def __init__(self) -> None:
        self.nxt: Optional[Node] = None
        self.val: int = 0


def main() -> None:
    a = Node()
    if nondet_bool():
        a.nxt = Node()
    __ESBMC_assume(a.nxt is not None)
    x = a.nxt.val


main()
