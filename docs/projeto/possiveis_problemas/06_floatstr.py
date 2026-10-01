def main() -> None:
    raw: str = "abc"
    if nondet_bool():
        raw = "1.5"
    x: float = float(raw)
    assert x != -7777.0
main()
