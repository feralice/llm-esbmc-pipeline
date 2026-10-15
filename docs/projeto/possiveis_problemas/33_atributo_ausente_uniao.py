# CPython: AttributeError ('B' object has no attribute 'size') quando nondet_bool() é verdadeiro.
# ESBMC master: VERIFICATION SUCCESSFUL.
from typing import Union


class A:
    def __init__(self) -> None:
        self.size: int = 1


class B:
    def __init__(self) -> None:
        self.name: str = "b"


def get_size(x: Union[A, B]) -> int:
    return x.size


def main() -> None:
    x: Union[A, B] = A()
    if nondet_bool():
        x = B()
    get_size(x)


main()
