# CPython: IndexError (index out of range), exit 1.
# ESBMC master 822227ff96 (08/11/2026): "Generated 0 VCC(s)" e VERIFICATION SUCCESSFUL. Falso negativo.
# `x = d[0]` sozinho e `d[0] == 80` dão FAILED (certo); só `d[0] == b"P"` perde a checagem do índice.
# Contorno que preserva o comportamento: `len(d) > 0 and d[0] == b"P"`. Achado em cps_gps_60 (Adafruit GPS).
# O reprodutor do subagente usava nondet_bool(), que o CPython não tem; esta forma com f(b"") vale nos dois.
def f(d: bytes) -> int:
    if d[0] == b"P":
        return 1
    return 0


f(b"")
