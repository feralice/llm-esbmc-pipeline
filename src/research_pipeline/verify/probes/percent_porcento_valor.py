# Regra compat_percent_format. Sonda nova: %% literal, par valor (o valor certo é '5%').
def label(n: int) -> str:
    return "%d%%" % (n,)


def main() -> None:
    n: int = nondet_int()
    __ESBMC_assume(n == 5)
    s: str = label(n)
    assert s == '5%'


main()
