# Regra compat_percent_format. Sonda nova: %d de float trunca, par violacao (o valor certo é '2').
def label(x: float) -> str:
    return "%d" % (x,)


def main() -> None:
    x: float = nondet_float()
    __ESBMC_assume(x == 2.75)
    s: str = label(x)
    assert s != '2'


main()
