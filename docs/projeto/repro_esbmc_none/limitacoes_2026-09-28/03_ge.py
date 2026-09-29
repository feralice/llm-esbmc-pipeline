from typing import Optional
def f(limit: Optional[int], n: int) -> bool:
    return n >= limit
def main() -> None:
    limit: Optional[int] = None
    if nondet_bool():
        limit = 5
    r: bool = f(limit, 3)
    assert r or not r
main()
