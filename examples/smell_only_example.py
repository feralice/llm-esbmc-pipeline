def process_order(a: int, b: int, c: int, d: int, e: int, f: int) -> int:
    total = a + b

    if total > 10:
        total += c
    else:
        total -= c

    if total % 2 == 0:
        total += d
    else:
        total -= d

    if total > 20:
        total += e
    else:
        total -= e

    if total < 5:
        total += f
    else:
        total -= f

    return total


def main() -> None:
    result = process_order(3, 4, 5, 6, 7, 8)
    assert isinstance(result, int)


main()
