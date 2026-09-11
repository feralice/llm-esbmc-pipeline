# Comando: esbmc 01_divisao_por_zero.py
#
# Roda sem erro no interpretador Python normal (random.random() nunca dá
# exatamente 0.0 na pratica), mas o ESBMC prova que existe um caminho onde
# cond e x viram 0 depois do cast pra int, e ai 42 // x quebra.
#
# Saida real (ESBMC 8.4.0, verificada nesta maquina):
#   Violated property:
#     file 01_divisao_por_zero.py line 19 column 8 function div1
#     division by zero
#     CWE: CWE-369
#     x != 0
#   VERIFICATION FAILED

import random as rand


def div1(cond: int, x: int) -> int:
    if not cond:
        return 42 // x
    else:
        return x // 10


cond: int = rand.random()
x: int = rand.random()

assert div1(cond, x) != 1
