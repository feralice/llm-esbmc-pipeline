# Regra none_guards_call. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.status: Optional[str] = None
        if nondet_bool():
            self.status = "7"


def main() -> None:
    b = Box()
    code = int(b.status)


main()
