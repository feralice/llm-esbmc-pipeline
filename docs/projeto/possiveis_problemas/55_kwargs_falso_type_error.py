# CPython: executa sem erro (g recebe a=1 do dicionário).
# ESBMC master 4a356e33eb: VERIFICATION FAILED com "uncaught exception: TypeError", um falso positivo.
# O mesmo acontece com def f(**kw): return g(**kw) chamado como f(a=1). Achado na redução do 54.
def g(a):
    return a


d = {"a": 1}
g(**d)
