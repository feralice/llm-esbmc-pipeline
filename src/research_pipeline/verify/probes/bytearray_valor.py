# Regra compat_bytearray. ESBMC recusa bytearray; a regra troca por lista de inteiros.
def f(n: int) -> int:
    buf = bytearray(n)
    buf.append(3)
    return len(buf)


r = f(2)
assert r == 3
