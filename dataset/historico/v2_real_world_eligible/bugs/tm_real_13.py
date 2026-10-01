def xg_characters(serialized_value: int) -> str:
    # Real code (scrapy/exporters.py, XmlItemExporter._xg_characters, pre-fix
    # bb2cf7c0): a non-text serialized value (e.g. an int field) reaches
    # serialized_value.decode(self.encoding).
    return serialized_value.decode("utf-8")


def main() -> None:
    xg_characters(3)


main()
