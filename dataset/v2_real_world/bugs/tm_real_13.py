def export_xml_field_value(is_text: bool) -> None:
    # Real code (scrapy/exporters.py:XmlItemExporter._export_xml_field,
    # BugsInPy scrapy bug #22): a serialized field value that isn't
    # list-like falls into `self._xg_characters(serialized_value)`
    # unconditionally. _xg_characters() calls `.decode(self.encoding)` on
    # anything that isn't already text -- if serialized_value is an int or
    # float (a numeric item field), it has no .decode() method, raising
    # AttributeError. Fix converts non-text values with str(...) first.
    assert is_text


def main() -> None:
    is_text: bool = nondet_bool()
    export_xml_field_value(is_text)


main()
