# CPython: AssertionError (h.item é B, não A).
# ESBMC master: VERIFICATION SUCCESSFUL. Com um atributo em cada classe, ou com x local, dá FAILED.
class A:
    pass


class B:
    pass


class Holder:
    def __init__(self, item: object) -> None:
        self.item = item


def main() -> None:
    h = Holder(B())
    assert isinstance(h.item, A)


main()
