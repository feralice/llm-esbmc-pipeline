# Regra properties_as_attributes. Sonda nova: o 8.5 não tinha property.
class Account:
    def __init__(self) -> None:
        self.total: int = 0

    @property
    def share(self) -> int:
        return 10 // self.total


def main() -> None:
    a = Account()
    x = a.share


main()
