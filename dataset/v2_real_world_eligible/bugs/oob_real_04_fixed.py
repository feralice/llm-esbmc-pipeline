# Fix thefuck e2e8b6fc: only index self._cached[0] when self._cached is non-empty.
def realise(cached: list) -> int:
    if cached:
        return cached[0]
    return -1


def main() -> None:
    cached: list = []
    realise(cached)


main()
