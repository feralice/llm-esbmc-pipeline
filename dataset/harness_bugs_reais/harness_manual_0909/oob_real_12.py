def fast_float(x: str) -> str:
    first: str = x[0]
    return first


def main() -> None:
    is_empty: bool = nondet_bool()
    x: str = "" if is_empty else "5"
    fast_float(x)


main()
