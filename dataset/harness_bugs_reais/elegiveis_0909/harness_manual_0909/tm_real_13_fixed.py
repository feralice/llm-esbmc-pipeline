# Fix scrapy bb2cf7c0: non-text values go through str(serialized_value) first.
def xg_characters(serialized_value: int) -> str:
    return str(serialized_value)


def main() -> None:
    xg_characters(3)


main()
