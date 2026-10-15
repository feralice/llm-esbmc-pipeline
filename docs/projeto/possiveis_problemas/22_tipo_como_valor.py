def check(data: int, s: type) -> int:
    if isinstance(data, s):
        return 10 // data
    return 0


def main() -> None:
    check(0, int)


main()
