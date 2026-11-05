# CPython: executa sem erro (value[1] == 2.5).
# ESBMC master 451f54c e d520: "ESBMC caught SIGSEGV" (exit 139) no encoder; com --z3, tipos
# "tuple" e "struct_type_tag-tuple_bool_floatbv" incompatíveis. Também tuple[float, bool] e tuple[int, bool]
# (exit 70, exceção do Bitwuzla). tuple[bool, bool], tuple[int, float] e tuple[float, float] dão o certo.
# É o caso da #9843 que o #9863 não cobre: tupla com bool junto de um tipo mais largo (há membro de padding).
from typing import Optional

try:
    from esbmc import nondet_bool
except ImportError:
    def nondet_bool() -> bool:
        return True


value: Optional[tuple[bool, float]] = None
if nondet_bool():
    value = (True, 2.5)
if value is not None:
    assert value[1] == 2.5
