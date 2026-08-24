def buggy_is_chunked(value: str) -> bool:
    # Real code (tornado/http1connection.py, BugsInPy tornado bug #11):
    # case-sensitive comparison misses 'Chunked'/'CHUNKED' Transfer-Encoding
    # header values that real servers send.
    return value == "chunked"


def correct_is_chunked(value: str) -> bool:
    return value.lower() == "chunked"


def main() -> None:
    value: str = "Chunked"
    assert buggy_is_chunked(value) == correct_is_chunked(value)


main()
