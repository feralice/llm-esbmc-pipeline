def build_status(code: int, retries: int, timeout: int) -> str:
    status = "ok"
    if code >= 500:
        status = "server"
    elif code >= 400:
        status = "client"
    elif code >= 300:
        status = "redirect"
    if retries > 0:
        status = status + ":retry"
    if retries > 3:
        status = status + ":many"
    if timeout > 10:
        status = status + ":slow"
    if timeout > 60:
        status = status + ":timeout"
    return status