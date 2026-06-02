# Extracted from httpie/downloads.py — httpie project
# Bug: downloaded / total_size raises ZeroDivisionError when Content-Length header is absent (total_size == 0)
# Real fix: guarded with "if self.total_size else 0"
# Source: httpie download progress tracker
def compute_download_percentage(downloaded: int, total_size: int) -> float:
    return downloaded / total_size * 100
