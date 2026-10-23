# CPython: IndexError (index out of range).
# ESBMC master 7da3564: recusa (cannot determine the length of a `-> bytes` return value for 'encode').
def encode() -> bytes:
    return b"ab"


x = encode()[2]
