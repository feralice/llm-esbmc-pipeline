# CPython: ValueError.
# ESBMC master 7da3564: VERIFICATION SUCCESSFUL; sem o str() em volta, FAILED com ValueError.
def label() -> str:
    raise ValueError("x")


s = str(label())
