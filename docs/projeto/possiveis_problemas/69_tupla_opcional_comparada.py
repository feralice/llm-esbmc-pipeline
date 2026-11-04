# CPython: executa sem erro (1.5 < 2.0).
# ESBMC master 0945ac9: Bitwuzla "term with unexpected sort" (exit 70); --z3: "Sorts Optional_struct ... tuple".
# Gatilho: Optional[tuple[...]] anotado, atribuído num ramo nondet, elemento comparado. Sem a anotação dá o
# veredito certo, mas no harness real (cps_mavproxy_1380) tirar a anotação gera outro erro de conversão.
from typing import Optional

try:
    from esbmc import nondet_bool
except ImportError:
    def nondet_bool() -> bool:
        return True


value: Optional[tuple[float, float]] = None
if nondet_bool():
    value = (1.5, 2.5)
if value is not None:
    assert value[0] < 2.0
