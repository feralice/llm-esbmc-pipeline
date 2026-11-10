# Regra compat_bytearray. Gêmeo de bytearray_valor com o assert trocado.
def f(n: int) -> int:
    buf = bytearray(n)
    buf.append(3)
    return len(buf)


r = f(2)
assert r == 4
