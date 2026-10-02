def get_loader_class(loader_val: int, manager_val: int) -> int:
    # Real code (scrapy/crawler.py:192-193, _get_spider_loader):
    # `settings.get('SPIDER_LOADER_CLASS', settings.get('SPIDER_MANAGER_CLASS'))`
    # gives the newer SPIDER_LOADER_CLASS setting priority over the
    # deprecated-but-still-honored SPIDER_MANAGER_CLASS. When a project has
    # both configured during the deprecation window, the real precondition
    # (the deprecation warning issued right above this line) says
    # SPIDER_MANAGER_CLASS should still win until fully removed. Fixed to
    # `settings.get('SPIDER_MANAGER_CLASS', settings.get('SPIDER_LOADER_CLASS'))`.
    result: int = loader_val
    return result


def main() -> None:
    loader_val: int = nondet_int()
    manager_val: int = nondet_int()
    __ESBMC_assume(loader_val != manager_val)
    result: int = get_loader_class(loader_val, manager_val)
    assert result == manager_val


main()
