def follow_url(url_is_none: bool) -> None:
    # Real code (scrapy/http/response/__init__.py, Response.follow,
    # BugsInPy scrapy#5): pre-fix, `follow()` only special-cases a `Link`
    # instance (`if isinstance(url, Link): url = url.url`) before calling
    # `self.urljoin(url)` unconditionally. urljoin (urllib.parse.urljoin
    # under the hood) requires a string and raises TypeError on None. The
    # fix adds an explicit `elif url is None: raise ValueError(...)` before
    # urljoin runs. ESBMC-Python does not model urllib.parse, so the crash
    # is made explicit via assert on the precondition it depends on.
    assert not url_is_none


def main() -> None:
    url_is_none: bool = nondet_bool()
    follow_url(url_is_none)


main()
