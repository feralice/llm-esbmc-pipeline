from typing import Optional


def first_chunk_flag(num: str, decimal: Optional[str]) -> bool:
    # Real code (inflect.py, numwords, pre-fix f799157f): decimal=None is a valid
    # argument, but num.endswith(decimal) is called unconditionally.
    return not num.endswith(decimal)


def main() -> None:
    decimal: Optional[str] = None
    if nondet_bool():
        decimal = "point"
    first_chunk_flag("one", decimal)


main()
