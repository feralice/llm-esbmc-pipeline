def buggy_should_chunk(has_content_length: bool, has_transfer_encoding: bool) -> bool:
    # Real code (tornado/http1connection.py:HTTP1Connection._read_body,
    # BugsInPy tornado #2): chunked encoding was chosen whenever no
    # Content-Length AND no Transfer-Encoding header was present at all,
    # missing the case where Transfer-Encoding is already explicitly
    # "chunked" (should still chunk, not skip).
    return (not has_content_length) and (not has_transfer_encoding)


def correct_should_chunk(has_content_length: bool, has_transfer_encoding: bool, transfer_encoding_val: str) -> bool:
    return (not has_content_length) and ((not has_transfer_encoding) or transfer_encoding_val == "chunked")


def main() -> None:
    has_content_length: bool = nondet_bool()
    has_transfer_encoding: bool = nondet_bool()
    transfer_encoding_val: str = "chunked"
    b: bool = buggy_should_chunk(has_content_length, has_transfer_encoding)
    c: bool = correct_should_chunk(has_content_length, has_transfer_encoding, transfer_encoding_val)
    assert b == c


main()
