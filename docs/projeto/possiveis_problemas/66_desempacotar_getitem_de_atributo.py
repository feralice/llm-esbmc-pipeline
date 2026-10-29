# CPython: executa sem erro (a, b = 1, 2).
# ESBMC master 4a356e33eb: "ERROR: Cannot unpack pointer - only tuples and arrays can be unpacked".
# Contorno que preserva o comportamento: mm: M = n.m; a, b = mm[0] (SUCCESSFUL).
# Reduzido de dz_real_04 (nki-samples interpolate_bilinear_2x_fwd); o harness do agente também tinha stub errado.
class M:
    def __getitem__(self, idx: int) -> tuple[int, int]:
        return 1, 2


class N:
    m: M = M()


n = N()
a, b = n.m[0]
assert a == 1
