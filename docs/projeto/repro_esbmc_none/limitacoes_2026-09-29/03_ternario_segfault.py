from typing import Optional


def up(name: Optional[str]) -> str:
    return name.upper()


def main() -> None:
    name: Optional[str] = None if nondet_bool() else nondet_str()
    up(name)


main()
