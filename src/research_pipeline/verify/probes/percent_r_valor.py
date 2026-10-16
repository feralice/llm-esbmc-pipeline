# Regra compat_percent_format. Sonda nova: %r de str constante, par valor (o valor certo é "7:'ab'").
def label(code: int) -> str:
    return "%d:%r" % (code, "ab")


def main() -> None:
    code: int = nondet_int()
    __ESBMC_assume(code == 7)
    s: str = label(code)
    assert s == "7:'ab'"


main()
