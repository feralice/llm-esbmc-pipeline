def unary_present(v: bool) -> bool:
    # Real code (youtube_dl/utils.py:_match_one, BugsInPy youtube-dl #1):
    # the '' filter operator meant "field is present", implemented as
    # `v is not None`. For a real boolean field, False is not None, so the
    # buggy check reported a False field as "present" -- wrong for a filter
    # meant to test truthiness, not nullness, of a bool.
    return v is not None


def main() -> None:
    v: bool = False
    result: bool = unary_present(v)
    assert not result


main()
