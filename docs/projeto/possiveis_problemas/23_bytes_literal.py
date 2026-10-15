def encode(n: int) -> bytes:
    return b"ab"


def main() -> None:
    b = encode(nondet_int())
    x = b[2]


main()
