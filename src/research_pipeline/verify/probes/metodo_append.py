# Regra builtin_named_methods_renamed. Origem: docs/projeto/possiveis_problemas/27_metodo_append_do_usuario.py.
class Store:
    def __init__(self) -> None:
        self.n: int = 0

    def append(self, k: int) -> int:
        return 10 // k


def main() -> None:
    s = Store()
    s.append(0)


main()
