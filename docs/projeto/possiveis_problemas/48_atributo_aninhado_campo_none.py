# CPython: AttributeError ('NoneType' object has no attribute 'next').
# ESBMC master 7da3564: ERROR: Cannot resolve nested attribute: next.
# Só converte quando `a.prev` recebeu um objeto antes no mesmo escopo; anotar `prev: "N"` não basta.
class N:
    def __init__(self) -> None:
        self.prev = None
        self.next = None


def f() -> None:
    a = N()
    a.prev.next = None


f()
