# Regra compat_percent_format. Sonda nova: %s de float, par violacao (o valor certo é 'v=1.5').
def label(x: float) -> str:
    return "v=%s" % (x,)


def main() -> None:
    x: float = nondet_float()
    __ESBMC_assume(x == 1.5)
    s: str = label(x)
    assert s != 'v=1.5'


main()
