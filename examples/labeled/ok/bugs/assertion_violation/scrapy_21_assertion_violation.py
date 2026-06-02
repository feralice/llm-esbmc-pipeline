# Extracted from scrapy/http/request/__init__.py — Scrapy web scraping framework
# Source: BugsInPy scrapy #21
# Bug: assert method.upper() in SUPPORTED_METHODS fires for non-standard HTTP methods
# Real fix: method validation moved to a warning instead of assertion
SUPPORTED_METHODS = ("GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS")

def build_request(url: str, method: str) -> dict:
    assert method.upper() in SUPPORTED_METHODS, f"Unsupported HTTP method: {method}"
    return {"url": url, "method": method.upper()}
