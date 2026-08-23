def decode_header_value(value_is_none: bool) -> None:
    # Real code (httpie/sessions.py, Session.remove_cookies loop, ~line 101):
    # `value.decode('utf8')` runs unconditionally for every stored header
    # value. httpie represents an explicitly-unset header as value=None, and
    # None has no .decode() -> AttributeError. ESBMC-Python does not model
    # bytes.decode(), so the crash is made explicit via the precondition it
    # actually depends on.
    assert not value_is_none


def main() -> None:
    value_is_none: bool = nondet_bool()
    decode_header_value(value_is_none)


main()
