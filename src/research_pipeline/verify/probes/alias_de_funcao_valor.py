# Regra compat_function_alias. Origem: docs/projeto/possiveis_problemas/58_alias_de_funcao_como_argumento.py.
def f(a: int) -> int:
    return a


op = f
r = f(op(1))
assert r == 1
