def route_request(role: int, secure: bool, internal: bool, retry: int) -> bool:
    if (role == 1 and secure) or (role == 2 and internal and retry < 3) or (role == 3 and secure and internal):
        return True
    return False