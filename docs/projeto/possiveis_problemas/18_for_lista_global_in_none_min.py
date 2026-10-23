# CPython: TypeError (argument of type 'NoneType' is not iterable).
# ESBMC master 7da3564: FAILED só por unwinding assertion em strstr, sem TypeError (igual com --unwind 30).
# Mesma causa do 26: `in` aplicado a uma str None.
from typing import Optional


def match(stderr: Optional[str]) -> bool:
    return 'ab' in stderr


match(None)
