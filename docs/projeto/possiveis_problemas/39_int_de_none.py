# CPython: TypeError (int() argument must be ... not 'NoneType') quando nondet_bool() é falso.
# ESBMC master: VERIFICATION SUCCESSFUL.
from typing import Optional


def main() -> None:
    status: Optional[str] = None
    if nondet_bool():
        status = "7"
    code = int(status)


main()
