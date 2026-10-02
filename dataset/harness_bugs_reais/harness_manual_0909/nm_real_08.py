class AppConfig:
    # Real code (sanic/request.py, Request.url_for, pre-fix e81a8ce0): SERVER_NAME
    # is only set on the app config when the user configures it.
    def __init__(self) -> None:
        self.KEEP_ALIVE: bool = True


def url_for(config: AppConfig) -> bool:
    server_name: str = config.SERVER_NAME
    if "//" in server_name:
        return True
    return False


def main() -> None:
    url_for(AppConfig())


main()
