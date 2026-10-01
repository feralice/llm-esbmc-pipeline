from typing import Optional
def f(classes: Optional[dict], tag: str) -> bool:
    return tag in classes
def main() -> None:
    classes: Optional[dict] = None
    if nondet_bool():
        classes = {"pre": "x"}
    f(classes, "pre")
main()
