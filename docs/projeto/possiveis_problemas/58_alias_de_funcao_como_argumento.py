# CPython: executa sem erro.
# ESBMC master 4a356e33eb: "ERROR: Function `py:...@op' type mismatch: expected code", depois
# "failed to find function" e core dump. Com x = op(1); f(x), ou f(f(1)) sem alias, dá SUCCESSFUL.
# Reduzido de bip_pandas_7 (np.where(op(l, r) | ..., ...) com op = operator.lt ou operator.le).
def f(a: int) -> int:
    return a


op = f
f(op(1))
