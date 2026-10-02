from typing import Optional


def to_bytes(text: Optional[str]) -> str:
    # scrapy/utils/python.py to_bytes: non-text input raises TypeError.
    if text is None:
        raise TypeError("to_bytes must receive a unicode, str or bytes object, got NoneType")
    return text


def host_header(has_netloc: bool) -> str:
    # Real code (scrapy/utils/request.py, request_httprepr, pre-fix 8d45b3c4):
    # urlparse(url).hostname is None for a URL without netloc (e.g. "file:///tmp/foo").
    hostname: Optional[str] = None
    if has_netloc:
        hostname = "example.com"
    return "Host: " + to_bytes(hostname)


def main() -> None:
    host_header(nondet_bool())


main()
