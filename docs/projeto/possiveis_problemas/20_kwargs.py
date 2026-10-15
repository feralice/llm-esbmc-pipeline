class Box:
    def __init__(self, **kw):
        self._error = kw.get('error')

    def div(self, n: int) -> int:
        return n // 0 if self._error is None else n


def main() -> None:
    b = Box()
    b.div(nondet_int())


main()
