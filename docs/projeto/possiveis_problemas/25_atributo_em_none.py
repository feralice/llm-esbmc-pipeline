# CPython: AttributeError ('NoneType' object has no attribute 'val') quando nondet_bool() é falso.
# ESBMC master: VERIFICATION SUCCESSFUL. Ler ou escrever n.val com n = None numa variável local dá o mesmo.
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
