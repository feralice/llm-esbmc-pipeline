# CPython: ZeroDivisionError dentro de Store.append.
# ESBMC master: VERIFICATION SUCCESSFUL; a chamada vai para o append de list. Com o nome remove, acusa
# ValueError de list.remove; com dois argumentos, recusa ("append() takes exactly one argument").
class Store:
    def __init__(self) -> None:
        self.n: int = 0

    def append(self, k: int) -> int:
        return 10 // k


def main() -> None:
    s = Store()
    s.append(0)


main()
