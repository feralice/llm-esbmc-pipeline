def url_for(server_name_missing: bool) -> None:
    # Real code (sanic/request.py, Request.url_for, BugsInPy sanic#4):
    # pre-fix, `if "//" in self.app.config.SERVER_NAME:` accesses
    # SERVER_NAME unguarded; SERVER_NAME may not be set on the app's
    # dynamic config object at all (AttributeError), not merely None. The
    # fix wraps the access in try/except AttributeError. ESBMC-Python
    # doesn't model dynamic per-instance attribute existence for a config
    # object shaped this way, so the crash is made explicit via assert on
    # the real precondition (config attribute present or not).
    assert not server_name_missing


def main() -> None:
    server_name_missing: bool = nondet_bool()
    url_for(server_name_missing)


main()
