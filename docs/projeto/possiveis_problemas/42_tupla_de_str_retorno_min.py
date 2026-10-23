# CPython: executa sem erro.
# ESBMC master 7da3564: ERROR: Incompatible struct in cast-to-struct (aborta, código 134).
def pair() -> tuple[str, str]:
    return ("x", nondet_str())


a, b = pair()
assert a == "x"
