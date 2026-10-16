# Regra none_guards_membership. Sonda nova.
from typing import Optional


def main() -> None:
    xs: Optional[list[str]] = None
    if nondet_bool():
        xs = ["a"]
    found = "a" in xs


main()
