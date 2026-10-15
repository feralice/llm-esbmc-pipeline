# CPython: ValueError não capturada (o except não cobre o bloco else).
# ESBMC master: VERIFICATION SUCCESSFUL; a exceção do else cai no except ValueError do mesmo try.
def parse(x: int) -> int:
    try:
        y = x + 1
    except ValueError:
        return 0
    else:
        raise ValueError("no else")
    return y


def main() -> None:
    parse(nondet_int())


main()
