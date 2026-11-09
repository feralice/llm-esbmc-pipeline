# CPython: executa sem erro.
# ESBMC master 822227ff96 (08/11/2026): "ERROR: bytearray is not supported; use bytes for an immutable byte sequence".
# Recusa intencional (PR #5515, mensagem clara no lugar do SIGABRT). Não achei issue pedindo suporte (08/11).
# Sem contorno fiel: bytes é imutável. Achado em cps_minimqtt_5 e cps_pythoncan_225.
def f(n: int) -> int:
    b = bytearray()
    b.append(n)
    return len(b)


assert f(1) == 1
