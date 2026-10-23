# CPython: ValueError não capturada (o except não cobre o bloco else).
# ESBMC master 7da3564: VERIFICATION SUCCESSFUL. Com except KeyError no lugar de ValueError, FAILED.
try:
    y = 1
except ValueError:
    pass
else:
    raise ValueError("e")
