class MetricsCollector:
    def configure_http_handler(self, handler: int) -> None:
        pass


class Metrics:
    pass


def get_handler_buggy(metrics: Metrics) -> None:
    metrics.configure_http_handler(1)


def main() -> None:
    m: Metrics = Metrics()
    get_handler_buggy(m)


main()
