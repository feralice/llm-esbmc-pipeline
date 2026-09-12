class HTTP1Connection:
    def _can_keep_alive(self, start_line, headers):
        if self.params.no_keep_alive:
            return False
        connection_header = headers.get("Connection")
        if connection_header is not None:
            connection_header = connection_header.lower()
        if start_line.version == "HTTP/1.1":
            return connection_header != "close"
        elif ("Content-Length" in headers
              or headers.get("Transfer-Encoding", "").lower() == "chunked"
              or start_line.method in ("HEAD", "GET")):
            return connection_header == "keep-alive"
        return False
