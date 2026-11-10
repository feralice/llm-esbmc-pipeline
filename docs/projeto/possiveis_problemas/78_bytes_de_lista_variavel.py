# CPython: executa sem erro (len(bytes([0, 0])) == 2).
# ESBMC master 95f025adf4 (09/11/2026): VERIFICATION FAILED em "assert len(b) == 2" (falso alarme).
# Com a lista literal dentro da chamada, bytes([0, 0, 3]) tem o tamanho certo. Só a lista em variável erra.
# Achado ao testar a reescrita bytearray -> lista de inteiros (compat_bytearray).
buf = [0, 0]
b = bytes(buf)
assert len(b) == 2
