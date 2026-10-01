def add(a: int, b: int) -> int:
    return a // b


def call_with(xs: list[int]) -> int:
    return add(*xs)


def main() -> None:
    xs: list[int] = [nondet_int(), nondet_int()]
    call_with(xs)


main()
