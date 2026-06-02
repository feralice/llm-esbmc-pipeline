# Extracted from scrapy/http/request/__init__.py — Scrapy web scraping framework
# Source: BugsInPy scrapy project / scrapy.Request.__init__()
# Smell: many parameters — 9 parameters including url, callback, method, headers,
# body, cookies, meta, encoding, priority, dont_filter, errback, flags
def init_request(url: str, callback=None, method: str = "GET", headers: dict = None,
                 body: bytes = None, cookies: dict = None, meta: dict = None,
                 encoding: str = "utf-8", priority: int = 0, dont_filter: bool = False,
                 errback=None, flags: list = None) -> dict:
    return {
        "url": url, "method": method.upper(), "headers": headers or {},
        "body": body or b"", "cookies": cookies or {}, "meta": meta or {},
        "encoding": encoding, "priority": priority, "dont_filter": dont_filter,
        "callback": callback, "errback": errback, "flags": flags or [],
    }
