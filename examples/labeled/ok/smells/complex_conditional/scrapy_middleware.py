# Extracted from scrapy/downloadermiddlewares/retry.py — Scrapy web scraping framework
# Source: BugsInPy scrapy project / RetryMiddleware.should_retry()
# Smell: complex conditional — combines response status, exception type, and settings
# across multiple nested conditions to decide whether to retry a request
def should_retry(response_status: int, exception_type: str, retry_count: int,
                 max_retries: int, retry_http_codes: list) -> bool:
    if retry_count >= max_retries:
        return False
    elif exception_type in ("ConnectionRefusedError", "TimeoutError", "DNSLookupError"):
        return True
    elif exception_type == "TunnelError":
        return True
    elif response_status and response_status in retry_http_codes:
        return True
    elif response_status == 429:
        return True
    elif response_status and 500 <= response_status < 600 and response_status != 501:
        return True
    else:
        return False
