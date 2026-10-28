# CPython: executa sem erro (1 < 2, o assert passa).
# ESBMC master 4a356e33eb: VERIFICATION FAILED no assert, um falso positivo.
# Com os parâmetros de lt anotados (a: int, b: int) dá SUCCESSFUL. Achado na redução do 58.
class Operator:
    def lt(self, a, b):
        return a < b


operator = Operator()


def f(x: int, y: int) -> bool:
    op = operator.lt
    return op(x, y)


assert f(1, 2)
