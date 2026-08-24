def encode_hostname(hostname_is_none: bool) -> None:
    # Real code (scrapy/utils/request.py:82, request_httprepr):
    # `to_bytes(parsed.hostname)` ran unconditionally. `urlparse(...).
    # hostname` is None for a URL with no netloc (relative/malformed
    # request), and `to_bytes(None)` raises TypeError instead of the fixed
    # `to_bytes(parsed.hostname or b'')`. ESBMC-Python does not model
    # `to_bytes()`'s internals, so the crash is made explicit via the real
    # precondition it silently depended on.
    assert not hostname_is_none


def main() -> None:
    hostname_is_none: bool = nondet_bool()
    encode_hostname(hostname_is_none)


main()
