# CPython: executa sem erro (nondet_bool() é True e o `or` não avalia c.limit).
# ESBMC master 4a356e33eb: "ERROR: Can't generate zero for type empty" e aborta.
# Gatilho: atributo inexistente como operando de or/and na condição de if/while. Contorno: separar em elif.
# Reduzido de nm_real_25 (tornado HTTP1Connection._can_keep_alive). Ver o 62, mesma raiz.
try:
    from esbmc import nondet_bool
except ImportError:
    def nondet_bool() -> bool:
        return True


class C:
    pass


c = C()
if nondet_bool() or c.limit:
    pass
