def crawler_process_init(settings_is_dict: bool) -> None:
    # Real code (scrapy/crawler.py:CrawlerProcess.__init__, BugsInPy scrapy
    # bug #32): super().__init__(settings) normalizes a plain dict into a
    # Settings object and stores it as self.settings, but the buggy code
    # calls configure_logging(settings)/log_scrapy_info(settings) with the
    # original (possibly still-a-dict) local parameter instead of
    # self.settings. configure_logging() calls .getbool() on it, which a
    # plain dict does not have.
    assert not settings_is_dict


def main() -> None:
    settings_is_dict: bool = nondet_bool()
    crawler_process_init(settings_is_dict)


main()
