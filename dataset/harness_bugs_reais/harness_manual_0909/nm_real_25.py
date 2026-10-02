def check_keep_alive(is_request_line: bool) -> None:
    # Real code (tornado/http1connection.py:HTTP1Connection._can_keep_alive,
    # BugsInPy tornado bug #13): `start_line.method in ("HEAD", "GET")` runs
    # unconditionally in the elif branch. `start_line` can be either a
    # request start line (has .method) or a response start line (has no
    # .method attribute at all), so a response passed through this path
    # raises AttributeError. Fixed to `getattr(start_line, 'method', None)`.
    assert is_request_line


def main() -> None:
    is_request_line: bool = nondet_bool()
    check_keep_alive(is_request_line)


main()
