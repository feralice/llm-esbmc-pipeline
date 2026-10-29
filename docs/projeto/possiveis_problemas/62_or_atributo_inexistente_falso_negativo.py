# CPython: AttributeError ('C' object has no attribute 'limit').
# ESBMC master 4a356e33eb: VERIFICATION SUCCESSFUL (falso negativo silencioso), mesma raiz do 61.
class C:
    pass


def f(c):
    x = False or c.limit
    return x


f(C())
