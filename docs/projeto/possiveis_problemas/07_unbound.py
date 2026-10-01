def f(d: dict) -> int:
    for k in d.keys():
        pass
    return k
def main() -> None:
    r: int = f({})
    assert r != -7777
main()
