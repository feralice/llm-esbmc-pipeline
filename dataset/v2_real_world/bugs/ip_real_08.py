def buggy_netloc(server_name: str, has_host: bool, host_val: str) -> str:
    # Real code (sanic/app.py:Sanic.url_for, BugsInPy sanic #3): before the
    # fix, a `host` segment embedded in the route's `uri` (split off via
    # `uri.find("/")` slicing) was never extracted, so `netloc` always fell
    # back to the app's configured SERVER_NAME even when the route itself
    # specified a different host.
    return server_name


def correct_netloc(server_name: str, has_host: bool, host_val: str) -> str:
    if has_host:
        return host_val
    return server_name


def main() -> None:
    has_host: bool = nondet_bool()
    server_name: str = "default.example"
    host_val: str = "custom.example"
    b: str = buggy_netloc(server_name, has_host, host_val)
    c: str = correct_netloc(server_name, has_host, host_val)
    assert b == c


main()
