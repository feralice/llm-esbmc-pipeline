class HTTP1Connection:
    def write_headers(self, is_post_put_patch: bool, headers: dict) -> bool:
        """Reduced from tornado/http1connection.py, pre-fix."""
        self._chunking_output: bool = (
            is_post_put_patch
            and "Content-Length" not in headers
            and "Transfer-Encoding" not in headers
        )
        return self._chunking_output
