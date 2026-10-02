# Fix inflect f799157f: first = True when decimal is None.
from typing import Optional


def first_chunk_flag(num: str, decimal: Optional[str]) -> bool:
    if decimal is None:
        return True
    return not num.endswith(decimal)


def main() -> None:
    decimal: Optional[str] = None
    if nondet_bool():
        decimal = "point"
    first_chunk_flag("one", decimal)


main()
