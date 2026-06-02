# Extracted from tornado/websocket.py — Tornado web framework
# Source: BugsInPy tornado #1
# Bug: assert self.stream is not None fires after WebSocket connection is closed
# Real fix: changed to assert self.ws_connection is not None
def set_nodelay(stream, value: bool) -> None:
    assert stream is not None
    stream.set_nodelay(value)
