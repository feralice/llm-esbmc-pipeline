# Regra compat_percent_format. Sonda nova: %d de bool, par violacao (o valor certo é '1').
def label(b: bool) -> str:
    return "%d" % (b,)


def main() -> None:
    b: bool = nondet_bool()
    __ESBMC_assume(b)
    s: str = label(b)
    assert s != '1'


main()
