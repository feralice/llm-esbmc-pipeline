# CPython: executa.
# ESBMC master 7da3564: ERROR: Cannot unpack empty - only tuples and arrays can be unpacked.
# Com h definida antes de g: VERIFICATION SUCCESSFUL. Métodos da mesma classe dão o mesmo erro.
def g(x: int) -> tuple[int, int]:
    b, a = h(x)
    return b, a


def h(x: int) -> tuple[int, int]:
    return x, 0


r = g(2)
assert r[0] >= 0
# Contorno que NÃO serve: guardar o retorno numa variável anotada antes de desempacotar
# (`_t: tuple[int, int] = h(x); b, a = _t`) é aceito, mas o ESBMC calcula o valor errado:
# `assert r[0] == 2` dá FAILED (falso positivo). Só reordenar (h antes de g) dá o resultado certo.
