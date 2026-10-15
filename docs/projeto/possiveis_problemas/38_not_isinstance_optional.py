# CPython: TypeError (not a string) quando text fica None.
# ESBMC master: VERIFICATION SUCCESSFUL; o mesmo teste com text local dá FAILED.
from typing import Optional


def check(text: Optional[str]) -> str:
    if not isinstance(text, str):
        raise TypeError("not a string")
    return text


def main() -> None:
    text: Optional[str] = None
    if nondet_bool():
        text = "a"
    check(text)


main()
