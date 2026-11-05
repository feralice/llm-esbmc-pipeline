# CPython: executa sem erro (len de uma tupla de 2 elementos é 2).
# ESBMC master 451f54c: FAILED falso em len(value) == 2 (o len vira strlen sobre a struct Optional e dá 1;
# com == 1, SUCCESSFUL). `for v in value` também conta 1 volta. No d520 o len e o for davam o certo.
# Gatilho: Optional[tuple[...]] anotado, atribuído num ramo, lido depois do `is not None`. Apareceu com o
# #9863 (correção da #9843), que passou a embrulhar a tupla no Optional; índice, `in` e `==` ficaram certos.
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
    assert len(value) == 2
