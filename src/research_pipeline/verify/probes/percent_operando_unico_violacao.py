# Regra compat_percent_format. Sonda nova: operando único fora de tupla, par violacao (o valor certo é 'id=7').
def label(code: int) -> str:
    return "id=%s" % code


def main() -> None:
    code: int = nondet_int()
    __ESBMC_assume(code == 7)
    s: str = label(code)
    assert s != 'id=7'


main()
