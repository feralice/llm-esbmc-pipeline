# CPython: TypeError (object of type 'C' has no len()).
# ESBMC master 7da3564: VERIFICATION SUCCESSFUL. Fora de condição (n = len(c)) dá FAILED com TypeError.
# O mesmo vale para atributo ausente: `if c.limit:` dá SUCCESSFUL, `x = c.limit` dá FAILED com AttributeError.
class C:
    pass


c = C()
if len(c) > 0:
    pass
