# CPython: AssertionError quando nondet_bool() é falso (text continua None).
# ESBMC master: VERIFICATION SUCCESSFUL. Com text = "a" no lugar de nondet_str(), ou com
# Optional[int] e nondet_int(), dá FAILED.
from typing import Optional


def main() -> None:
    text: Optional[str] = None
    if nondet_bool():
        text = nondet_str()
    assert text is not None


main()
