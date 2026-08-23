def truncate_title(video_title: str) -> str:
    # Real code (youtube_dl/extractor/facebook.py, FacebookIE._real_extract,
    # pre-fix inline logic, BugsInPy youtube-dl#39): `_html_search_regex(...,
    # default=None)` may leave video_title as None when the caption span
    # isn't found on the page. The pre-fix truncation has no None guard, so
    # len(video_title) dereferences a NULL string -- CWE-476. The fix
    # extracts this into `limit_length(s, length)`, which returns None
    # immediately when s is None.
    if len(video_title) > 80 + 3:
        video_title = video_title[:80] + '...'
    return video_title


def main() -> None:
    has_title: bool = nondet_bool()
    # Gotcha: `x if has_title else None` (ternary) does NOT preserve
    # NULL-pointer semantics for a str-annotated variable in ESBMC-Python --
    # verified separately that it silently verifies SUCCESSFUL instead of
    # hitting the real len(NULL) crash. An if/else assignment does.
    video_title: str = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    if not has_title:
        video_title = None
    truncate_title(video_title)


main()
