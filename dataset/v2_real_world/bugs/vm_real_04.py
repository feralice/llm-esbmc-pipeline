def negated_filter_buggy(attr_matches: bool) -> bool:
    # Real code (youtube_dl/YoutubeDL.py:_build_format_filter, BugsInPy
    # youtube-dl bug #12): `op = lambda attr, value: not str_op` negates the
    # str_op FUNCTION OBJECT itself (always truthy) instead of calling
    # str_op(attr, value) and negating the result. A negated string filter
    # (e.g. "ext!=mp4") always evaluates to False, regardless of the actual
    # attribute value.
    return False


def negated_filter_correct(attr_matches: bool) -> bool:
    return not attr_matches


def main() -> None:
    attr_matches: bool = nondet_bool()
    buggy: bool = negated_filter_buggy(attr_matches)
    correct: bool = negated_filter_correct(attr_matches)
    assert buggy == correct


main()
