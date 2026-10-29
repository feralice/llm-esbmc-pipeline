# CPython: executa sem erro (apply devolve 2).
# ESBMC master 4a356e33eb: "ERROR: Variable 'p' is not defined in function 'lam1' at line 12."
# Mesmo programa com run() como função livre dá SUCCESSFUL; @staticmethod também falha.
# Contorno: def de módulo no lugar do lambda (def aninhado no método também é recusado).
# Reduzido de dz_real_02 (ExactLanguageSearch.choose_best_split: min(..., key=lambda p: ...)).
def apply(f, x: int) -> int:
    return f(x)


class S:
    def run(self) -> int:
        return apply(lambda p: p + 1, 1)


assert S().run() == 2
