# Extracted from black.py — Black code formatter
# Source: BugsInPy black #23
# Bug: raise AssertionError fires when the source cannot be parsed by lib2to3
# Real fix: exception context was corrected to expose the original parse error
def parse_source(can_parse: bool) -> str:
    if not can_parse:
        raise AssertionError("cannot parse source")

    return "parsed"