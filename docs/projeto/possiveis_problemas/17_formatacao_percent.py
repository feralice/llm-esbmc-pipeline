def label(code: int, name: str) -> str:
    return "%s %s" % (code, name)


def main() -> None:
    code: int = nondet_int()
    name: str = nondet_str()
    s: str = label(code, name)
    assert len(s) > 0


main()
