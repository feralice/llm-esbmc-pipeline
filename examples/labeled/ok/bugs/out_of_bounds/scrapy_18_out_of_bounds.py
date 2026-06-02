# Extracted from scrapy/http/headers.py — Scrapy web scraping framework
# Source: BugsInPy scrapy #18
# Bug: split(';')[1] raises IndexError when Content-Disposition header has no semicolon
# Real fix: added guard checking len(parts) > 1 before indexing
def extract_filename(content_disposition: str) -> str:
    filename = content_disposition.split(";")[1].split("=")[1]
    return filename.strip("\"'")