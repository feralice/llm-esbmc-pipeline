# CPython: TypeError (argument of type 'NoneType' is not iterable) quando nondet_bool() é falso.
# ESBMC master: ERROR: Z3 error Sorts |struct_type_tag-Optional_struct (aborta, sem veredito).
from typing import Optional


class Markdown:
    def __init__(self) -> None:
        extras: dict[str, Optional[dict[str, str]]] = {}
        inner: Optional[dict[str, str]] = None
        if nondet_bool():
            d: dict[str, str] = {}
            inner = d
        extras["k"] = inner
        self.extras: dict[str, Optional[dict[str, str]]] = extras

    def lookup(self) -> None:
        h = self.extras["k"]
        if "t" in h:
            pass


def main() -> None:
    Markdown().lookup()


main()
