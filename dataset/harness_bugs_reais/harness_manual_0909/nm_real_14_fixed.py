# esbmc: --unwind 40 --timeout 150s
# Fix scrapy 8d45b3c4: to_bytes(parsed.hostname or b'').
from typing import Optional


def to_bytes(text: Optional[str]) -> str:
    if text is None:
        raise TypeError("to_bytes must receive a unicode, str or bytes object, got NoneType")
    return text


def host_header(has_netloc: bool) -> str:
    hostname: Optional[str] = None
    if has_netloc:
        hostname = "example.com"
    return "Host: " + to_bytes(hostname or "")


def main() -> None:
    host_header(nondet_bool())


main()
