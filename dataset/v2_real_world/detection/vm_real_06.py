class CrawlerRunner:
    def __init__(self, settings):
        if isinstance(settings, dict):
            settings = Settings(settings)
        self.settings = settings
        self.spider_loader = _get_spider_loader(settings)
        self._crawlers = set()
        self._active = set()


class CrawlerProcess(CrawlerRunner):
    def __init__(self, settings):
        super(CrawlerProcess, self).__init__(settings)
        install_shutdown_handlers(self._signal_shutdown)
        configure_logging(settings)
        log_scrapy_info(settings)
