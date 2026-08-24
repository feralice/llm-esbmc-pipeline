def check_bearer(scheme_is_bearer: bool, auto_error: bool) -> bool:
    # Real code (fastapi/security/http.py:114-119, HTTPBearer.__call__):
    # pre-fix always raised HTTPException on a non-bearer auth scheme,
    # ignoring self.auto_error entirely. Fixed to only raise when
    # auto_error is True, otherwise return None -- matching the
    # "optional auth" mode HTTPBearer already documents and already uses
    # for the missing-header case a few lines above.
    should_raise: bool = not scheme_is_bearer
    return should_raise


def main() -> None:
    scheme_is_bearer: bool = nondet_bool()
    auto_error: bool = nondet_bool()
    __ESBMC_assume(not scheme_is_bearer)
    __ESBMC_assume(not auto_error)
    should_raise: bool = check_bearer(scheme_is_bearer, auto_error)
    assert should_raise == auto_error


main()
