# Extracted from tornado/web.py — Tornado web framework
# Source: BugsInPy tornado project / RequestHandler.check_xsrf_cookie()
# Smell: complex conditional — combines method type, cookie presence,
# header presence, and whitelisting logic across deeply nested conditions
def check_xsrf_cookie(method: str, cookie_token: str, header_token: str,
                      argument_token: str, xsrf_cookie_version: int) -> bool:
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    elif not cookie_token:
        return False
    elif header_token and header_token == cookie_token:
        return True
    elif argument_token and argument_token == cookie_token:
        return True
    elif xsrf_cookie_version < 2 and len(cookie_token) == 32:
        return header_token == cookie_token or argument_token == cookie_token
    else:
        return False
