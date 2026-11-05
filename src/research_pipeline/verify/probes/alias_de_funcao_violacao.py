# Regra compat_function_alias. Gêmeo de alias_de_funcao_valor com o assert trocado.
def f(a: int) -> int:
    return a


op = f
r = f(op(1))
assert r == 2
