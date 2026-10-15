# CPython: TypeError (argument of type 'NoneType' is not iterable) quando s fica None.
# ESBMC master: VERIFICATION SUCCESSFUL. O #8249 cobriu dict e list, não str. Com d["k"] valendo None,
# só falha por unwinding assertion, sem TypeError.
from typing import Optional


def main() -> None:
    s: Optional[str] = None
    if nondet_bool():
        s = "xy"
    found = "ab" in s


main()
