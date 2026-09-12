def sitemap_urls_from_robots_ok(passed_text: bool) -> None:
    # Real code (scrapy/spiders/sitemap.py:SitemapSpider._parse_sitemap,
    # BugsInPy scrapy bug #20): calls sitemap_urls_from_robots(response.body)
    # -- response.body is bytes. Inside, `line.lstrip().startswith('Sitemap:')`
    # compares a bytes object against a str literal, raising
    # TypeError: startswith first arg must be bytes or a tuple of bytes, not str.
    # Fixed to pass response.text (str) instead.
    assert passed_text


def main() -> None:
    passed_text: bool = nondet_bool()
    sitemap_urls_from_robots_ok(passed_text)


main()
