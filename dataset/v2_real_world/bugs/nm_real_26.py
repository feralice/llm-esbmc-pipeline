def format_host_header(hostname_is_none: bool) -> None:
    # Pre-fix scrapy/utils/request.py (BugsInPy scrapy bug #29):
    # to_bytes(parsed.hostname) is called even when urlparse returns no host.
    assert not hostname_is_none


def main() -> None:
    format_host_header(True)


main()
