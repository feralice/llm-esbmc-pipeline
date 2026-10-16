# Regra compat_method_alias. Sonda nova: o 8.5 recusava "__repr__ = __str__" ("Variable __str__ not found").
class Box:
    def __init__(self) -> None:
        self.k: int = 0

    def ratio(self) -> int:
        return 10 // self.k

    share = ratio


def main() -> None:
    b = Box()
    b.share()


main()
