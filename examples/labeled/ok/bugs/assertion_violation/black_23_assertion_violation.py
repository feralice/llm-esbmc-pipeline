def parse_source(can_parse: bool) -> str:
    if not can_parse:
        raise AssertionError("cannot parse source")

    return "parsed"