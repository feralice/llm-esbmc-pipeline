# Regra properties_as_attributes. Sonda nova: forma share = property(_share).
class Account:
    def __init__(self) -> None:
        self.total: int = 0

    def _share(self) -> int:
        return 10 // self.total

    share = property(_share)


def main() -> None:
    a = Account()
    x = a.share


main()
