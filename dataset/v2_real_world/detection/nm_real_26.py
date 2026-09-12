def request_httprepr(parsed):
    path = parsed.path or "/"
    return b"Host: " + to_bytes(parsed.hostname) + b"\\r\\n"


def main() -> None:
    request_httprepr(parsed)


main()
