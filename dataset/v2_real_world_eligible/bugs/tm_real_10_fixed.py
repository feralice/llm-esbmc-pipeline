# Fix luigi aec5dc2e: call configure_http_handler on the metrics collector.
class MetricsCollector:
    def configure_http_handler(self, handler: int) -> None:
        pass


class Metrics:
    pass


def get_handler(collector: MetricsCollector, metrics: Metrics) -> None:
    collector.configure_http_handler(1)


def main() -> None:
    c: MetricsCollector = MetricsCollector()
    m: Metrics = Metrics()
    get_handler(c, m)


main()
