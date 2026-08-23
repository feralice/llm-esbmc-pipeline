def set_nodelay_guard(ws_connection_not_none: bool, stream_not_none: bool) -> None:
    # Real code (tornado/websocket.py:WebSocketHandler.set_nodelay):
    # `assert self.stream is not None`. In a WebSocketHandler, `self.stream`
    # is not what's guaranteed live once the handshake completes --
    # `self.ws_connection` is. The assert checks the wrong attribute, so it
    # fires even in the normal, correctly-connected case.
    __ESBMC_assume(ws_connection_not_none)
    assert stream_not_none


def main() -> None:
    ws_connection_not_none: bool = nondet_bool()
    stream_not_none: bool = nondet_bool()
    set_nodelay_guard(ws_connection_not_none, stream_not_none)


main()
