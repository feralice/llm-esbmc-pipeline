def compute_chunking_buggy(is_post_put_patch: bool, has_content_length: bool, has_transfer_encoding: bool) -> bool:
    return is_post_put_patch and not has_content_length and not has_transfer_encoding


def compute_chunking_fixed(is_post_put_patch: bool, has_content_length: bool, has_transfer_encoding: bool, transfer_encoding_is_chunked: bool) -> bool:
    te_ok: bool = (not has_transfer_encoding) or transfer_encoding_is_chunked
    return is_post_put_patch and not has_content_length and te_ok


def main() -> None:
    is_post_put_patch: bool = True
    has_content_length: bool = False
    has_transfer_encoding: bool = True
    transfer_encoding_is_chunked: bool = True
    buggy: bool = compute_chunking_buggy(is_post_put_patch, has_content_length, has_transfer_encoding)
    correct: bool = compute_chunking_fixed(is_post_put_patch, has_content_length, has_transfer_encoding, transfer_encoding_is_chunked)
    assert buggy == correct


main()
