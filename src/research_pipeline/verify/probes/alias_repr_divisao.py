# Regra compat_method_alias. Sonda nova: o caso documentado __repr__ = __str__, alcançado por repr().
class Box:
    def __init__(self) -> None:
        self.k: int = 0

    def __str__(self) -> str:
        return str(10 // self.k)

    __repr__ = __str__


def main() -> None:
    b = Box()
    r: str = repr(b)


main()
