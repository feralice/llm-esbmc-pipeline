from typing import Optional


class PamdRule:
    def __init__(self) -> None:
        self.prev: Optional[PamdRule] = None
        self.next: Optional[PamdRule] = None


def unlink(current_line: PamdRule) -> None:
    # Real code (ansible pamd.py, PamdService.remove, pre-fix a4b59d02): when the
    # matching rule is the last one, current_line.next is None.
    if current_line.prev is not None:
        current_line.prev.next = current_line.next
        current_line.next.prev = current_line.prev


def main() -> None:
    head: PamdRule = PamdRule()
    last: PamdRule = PamdRule()
    head.next = last
    last.prev = head
    unlink(last)


main()
