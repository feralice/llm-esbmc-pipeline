# CPython: ZeroDivisionError (t is float é verdadeiro).
# ESBMC master: VERIFICATION SUCCESSFUL; com t parâmetro do tipo type, t is float nunca é verdadeiro.
def width(t: type) -> int:
    if t is float:
        return 10 // 0
    return 1


def main() -> None:
    width(float)


main()
