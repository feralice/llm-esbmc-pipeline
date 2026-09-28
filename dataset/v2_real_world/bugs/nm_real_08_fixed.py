# Fix sanic e81a8ce0: wrap the SERVER_NAME check in try/except AttributeError.
class AppConfig:
    def __init__(self) -> None:
        self.KEEP_ALIVE: bool = True


def url_for(config: AppConfig) -> bool:
    try:
        server_name: str = config.SERVER_NAME
        if "//" in server_name:
            return True
    except AttributeError:
        pass
    return False


def main() -> None:
    url_for(AppConfig())


main()
