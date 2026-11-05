# CPython: executa sem erro (b == 2).
# ESBMC master 451f54c: "ERROR: Cannot unpack non-tuple type: tag-Optional_struct" (recusa); `a, *rest = value`
# também. No d520 o desempacotamento com * dava o certo e o `a, b = value` abortava o Bitwuzla (a #9843).
# Mesma origem do 70: o #9863 embrulha a tupla no Optional, e o desempacotamento não abre o Optional.
from typing import Optional

try:
    from esbmc import nondet_bool
except ImportError:
    def nondet_bool() -> bool:
        return True


value: Optional[tuple[int, int]] = None
if nondet_bool():
    value = (1, 2)
if value is not None:
    a, b = value
    assert b == 2
