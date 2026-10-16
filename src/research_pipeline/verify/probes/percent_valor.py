# Regra compat_percent_format. Origem: docs/projeto/possiveis_problemas/17_formatacao_percent.py.
def label(code: int, name: str) -> str:
    return "%s %d" % (name, code)


def main() -> None:
    code: int = nondet_int()
    __ESBMC_assume(code == 7)
    s: str = label(code, "ab")
    assert s == "ab 7"


main()
