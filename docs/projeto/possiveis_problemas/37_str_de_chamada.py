# CPython: ValueError levantada em label quando x > 0.
# ESBMC master: VERIFICATION SUCCESSFUL; sem o str() em volta, FAILED com ValueError.
def label(x: int) -> str:
    if x > 0:
        raise ValueError("positive")
    return "a"


def main() -> None:
    s = str(label(nondet_int()))


main()
