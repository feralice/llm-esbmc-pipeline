# Regra compat_method_alias. Sonda nova: par seguro de alias_repr_divisao (repr() devolve o valor de __str__).
class Box:
    def __init__(self) -> None:
        self.k: int = 2

    def __str__(self) -> str:
        return str(10 // self.k)

    __repr__ = __str__


def main() -> None:
    b = Box()
    r: str = repr(b)
    assert r == "5"


main()
