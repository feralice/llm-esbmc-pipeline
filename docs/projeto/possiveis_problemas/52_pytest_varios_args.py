# Gerador de pytest com três argumentos, só o terceiro decide o erro.
# ESBMC master 7da3564: o teste gerado tem só `c` e chama `f(c)` (TypeError: faltam `a` e `b`): o slicing tira
# os argumentos de que a violação não depende. Com --no-slice sai `f(a, b, c)` e o pytest reproduz o
# ZeroDivisionError. Guardar o nondet numa variável antes da chamada gera nomes internos (`z&0#1`), que não
# são Python válido.
def f(a: int, b: int, c: int) -> int:
    return (a + b) // c


f(nondet_int(), nondet_int(), nondet_int())
