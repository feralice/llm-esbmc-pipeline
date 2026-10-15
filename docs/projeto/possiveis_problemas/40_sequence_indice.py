# CPython: IndexError (list index out of range).
# ESBMC master: VERIFICATION SUCCESSFUL; com xs: list[str], FAILED com IndexError.
from typing import Sequence


def second(xs: Sequence[str]) -> str:
    return xs[1]


def main() -> None:
    second(["a"])


main()
