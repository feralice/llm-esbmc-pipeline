from typing import Optional
def f(t: Optional[int], s: int) -> int:
    return t * s
def main() -> None:
    t: Optional[int] = None
    if nondet_bool():
        t = 5
    r: int = f(t, 2)
    assert r != -7777
main()
