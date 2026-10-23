# Regra conditional_assignments_split. Origem: docs/historico/regras_pos_congelamento_2026-10-15.patch.
def scale(c: int, w: int) -> int:
    return 10 // w


def main() -> None:
    a: int = nondet_int()
    g = scale if a == 1 else (lambda c, w: scale(c, w))
    g(1, 0)


main()
