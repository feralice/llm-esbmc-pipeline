# Regra builtin_named_methods_renamed. Origem: variante get do 27 ("Dictionary variable not found").
class Codes:
    def __init__(self) -> None:
        self.n: int = 0

    def get(self, k: int) -> int:
        return 10 // k


def main() -> None:
    c = Codes()
    c.get(0)


main()
