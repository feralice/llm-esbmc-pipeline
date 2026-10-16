# Regra none_guards_attribute. Origem: docs/projeto/possiveis_problemas/25_atributo_em_none.py.
from typing import Optional


class Node:
    def __init__(self) -> None:
        self.nxt: Optional[Node] = None
        self.val: int = 0


def main() -> None:
    a = Node()
    if nondet_bool():
        a.nxt = Node()
    x = a.nxt.val


main()
