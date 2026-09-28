# Fix ansible a4b59d02: only touch current_line.next.prev when next is not None.
from typing import Optional


class PamdRule:
    def __init__(self) -> None:
        self.prev: Optional[PamdRule] = None
        self.next: Optional[PamdRule] = None


def unlink(current_line: PamdRule) -> None:
    if current_line.prev is not None:
        current_line.prev.next = current_line.next
        if current_line.next is not None:
            current_line.next.prev = current_line.prev


def main() -> None:
    head: PamdRule = PamdRule()
    last: PamdRule = PamdRule()
    head.next = last
    last.prev = head
    unlink(last)


main()
