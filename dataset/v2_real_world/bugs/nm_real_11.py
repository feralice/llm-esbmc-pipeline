def setitem_evict(limit_is_none: bool, limit: int, current_len: int) -> bool:
    # Real code (scrapy/utils/datatypes.py:315-318, LocalCache.__setitem__):
    # `while len(self) >= self.limit:` crashes with TypeError: '>=' not
    # supported between instances of 'int' and 'NoneType' when self.limit
    # is None (an unbounded cache). Fixed to `if self.limit: while ...`.
    assert not limit_is_none
    evicted: bool = False
    if not limit_is_none and current_len >= limit:
        evicted = True
    return evicted


def main() -> None:
    limit_is_none: bool = nondet_bool()
    limit: int = nondet_int()
    current_len: int = nondet_int()
    __ESBMC_assume(current_len >= 0)
    setitem_evict(limit_is_none, limit, current_len)


main()
